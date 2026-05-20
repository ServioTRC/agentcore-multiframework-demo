# Phase 4: Deploy to Amazon Bedrock AgentCore Runtime

Deploy the Invoice Processing Demo as a custom container on AgentCore Runtime in `us-east-1`.

## Prerequisites

- AWS CLI configured with appropriate permissions
- Docker with `buildx` (for ARM64 cross-compilation)
- Python 3.11+ with `boto3` installed
- An AWS account with Bedrock AgentCore access enabled

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  AgentCore Runtime (ARM64, us-east-1)               │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │  Custom Container (port 8080)               │    │
│  │  ┌─────────────┐  ┌──────────────────────┐ │    │
│  │  │ FastAPI      │  │ ADOT Auto-Instrument │ │    │
│  │  │ /invocations │  │ + Traceloop SDK      │ │    │
│  │  │ /ping        │  └──────────────────────┘ │    │
│  │  └──────┬──────┘                            │    │
│  │         │                                   │    │
│  │  ┌──────▼──────┐                            │    │
│  │  │ Strands     │                            │    │
│  │  │ Orchestrator│                            │    │
│  │  └──┬──────┬───┘                            │    │
│  │     │      │                                │    │
│  │  ┌──▼──┐ ┌─▼────────┐                      │    │
│  │  │Lang │ │ LangGraph │                      │    │
│  │  │Chain│ │ Validator │                      │    │
│  │  └─────┘ └──────────┘                      │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  OTEL Sidecar (localhost:4318) → CloudWatch/X-Ray   │
└─────────────────────────────────────────────────────┘
```

## Step-by-Step Deployment

### Step 1: Create the IAM Role

```bash
aws cloudformation deploy \
  --template-file deploy/iam_role.json \
  --stack-name agentcore-invoice-demo-role \
  --parameter-overrides AccountId=$(aws sts get-caller-identity --query Account --output text) \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

Verify the role was created:
```bash
aws iam get-role --role-name AgentCoreRuntimeRole --query 'Role.Arn' --output text
```

### Step 2: Build & Push Container to ECR

```bash
cd agentcore-invoice-demo
./deploy/build_and_push.sh $(aws sts get-caller-identity --query Account --output text) us-east-1
```

This script:
1. Creates the ECR repository (if it doesn't exist)
2. Authenticates Docker to ECR
3. Builds an ARM64 image using `docker buildx`
4. Pushes to ECR

### Step 3: Deploy to AgentCore Runtime

```bash
python -m deploy.deploy_agent \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --region us-east-1
```

The script will:
1. Call `create_agent_runtime` on the `bedrock-agentcore-control` API
2. Poll until the runtime status is `ACTIVE` (typically 2-5 minutes)
3. Print the Runtime ID for invocation

### Step 4: Enable Tracing (Console)

1. Open the [AgentCore Console](https://console.aws.amazon.com/bedrock/home?region=us-east-1#/agentcore)
2. Select **invoice-demo-agent**
3. Go to **Tracing** pane → **Edit** → **Enable** → **Save**

Also ensure CloudWatch Transaction Search is enabled:
1. CloudWatch Console → Application Signals → Transaction Search
2. Enable and select "Ingest spans as structured logs"

### Step 5: Test Invocation

Single prompt:
```bash
python -m deploy.invoke_agent \
  --runtime-id <RUNTIME_ID> \
  --prompt "What's the status of INV-001?"
```

Interactive mode:
```bash
python -m deploy.invoke_agent --runtime-id <RUNTIME_ID>
```

### Step 6: Verify Traces in CloudWatch

1. Open CloudWatch → Application Signals → Traces
2. Filter by service name: `agentcore-invoice-demo`
3. You should see a trace tree:
   - Root: AgentCore Runtime invocation
   - Child: `orchestrator.invoke` (Strands)
   - Grandchild: `tool.invoice_lookup` or `tool.invoice_validator`
   - Leaf: LangChain/LangGraph LLM calls

## File Reference

| File | Purpose |
|------|---------|
| `deploy/build_and_push.sh` | Build ARM64 Docker image and push to ECR |
| `deploy/deploy_agent.py` | Create AgentCore Runtime via control plane API |
| `deploy/invoke_agent.py` | Invoke the deployed agent via data plane API |
| `deploy/iam_role.json` | CloudFormation template for the IAM execution role |
| `Dockerfile` | Container definition (ARM64, port 8080, ADOT entrypoint) |

## API Reference

| Operation | Client | API |
|-----------|--------|-----|
| Create runtime | `bedrock-agentcore-control` | `create_agent_runtime` |
| Check status | `bedrock-agentcore-control` | `get_agent_runtime` |
| Invoke agent | `bedrock-agentcore` | `invoke_agent_runtime` |
| Delete runtime | `bedrock-agentcore-control` | `delete_agent_runtime` |

## Cleanup

```bash
# Delete the AgentCore Runtime
python -c "
import boto3
client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
client.delete_agent_runtime(agentRuntimeId='<RUNTIME_ID>')
print('Runtime deletion initiated')
"

# Delete ECR repository
aws ecr delete-repository --repository-name agentcore-invoice-demo --force --region us-east-1

# Delete IAM role stack
aws cloudformation delete-stack --stack-name agentcore-invoice-demo-role --region us-east-1
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Runtime stays in CREATING | Image pull failure | Verify ECR image exists and role has ECR permissions |
| Runtime FAILED | Container crash | Check CloudWatch logs at `/aws/bedrock/agent-runtime/` |
| No traces | Transaction Search disabled | Enable in CloudWatch console |
| LangChain traces missing | Traceloop not initialized | Verify `init_observability()` runs at startup |
| Timeout on invocation | Agent processing too long | Check model access and region availability |
| `UnknownServiceError` | boto3 too old | `pip install --upgrade boto3 botocore` |
