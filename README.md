# AgentCore Observability Demo: Multi-Framework Agent Tracing

A reference architecture demonstrating **full OpenTelemetry observability** across multiple AI agent frameworks (Strands Agents, LangChain, LangGraph) running on **Amazon Bedrock AgentCore Runtime** — proving that ADOT auto-instrumentation works seamlessly with any Python agent framework in a single container.

## Project Idea

This project addresses three common misconceptions about AgentCore:

1. ❌ "AgentCore Runtime cannot emit OTEL traces with LangChain/LangGraph agents"
2. ❌ "ADOT crashes with LangChain and LangGraph"
3. ❌ "ECS is a more mature deployment option"

**The demo proves all three wrong** by deploying a multi-framework agent system with full distributed tracing — from orchestrator through sub-agents — visible in CloudWatch GenAI Observability.

### What It Shows

| Capability | How It's Demonstrated |
|---|---|
| Framework-agnostic runtime | Strands, LangChain, and LangGraph coexist in one container |
| OTEL traces work | Full trace tree visible in CloudWatch (orchestrator → sub-agents → LLM calls) |
| Custom container = ECS-like DX | Same Dockerfile workflow, but with managed scaling and session isolation |
| Zero infra management | No ECS clusters, ALBs, or auto-scaling policies |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  AgentCore Runtime (ARM64, us-east-1)                   │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Custom Container (port 8080)                     │  │
│  │                                                   │  │
│  │  FastAPI (/invocations, /ping)                    │  │
│  │       │                                           │  │
│  │  Strands Orchestrator (routes user requests)      │  │
│  │       ├──────────────┐                            │  │
│  │       │              │                            │  │
│  │  LangChain       LangGraph                        │  │
│  │  Invoice Lookup  Invoice Validator                │  │
│  │  (retrieval)     (multi-step validation)          │  │
│  │                                                   │  │
│  │  ADOT + OpenLLMetry (Traceloop) → CloudWatch      │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Components

| Component | Framework | Role |
|---|---|---|
| Orchestrator | Strands Agents SDK | Routes user requests, invokes sub-agents as tools |
| Invoice Lookup | LangChain | Retrieves invoice status/details |
| Invoice Validator | LangGraph | Multi-step: extract → validate → flag discrepancies |
| Observability | ADOT + OpenLLMetry | Full OTEL traces to CloudWatch |

## Project Structure

```
agentcore-invoice-demo/
├── entrypoint.py           # FastAPI server (AgentCore service contract)
├── orchestrator.py         # Strands orchestrator agent
├── observability.py        # OTEL/ADOT + Traceloop configuration
├── main.py                 # Local interactive testing
├── tools/
│   ├── invoice_lookup.py   # LangChain sub-agent (Strands @tool wrapper)
│   └── invoice_validator.py# LangGraph sub-agent (Strands @tool wrapper)
├── data/
│   └── mock_invoices.py    # 3 sample invoices
├── deploy/
│   ├── build_and_push.sh   # Build ARM64 image → ECR
│   ├── deploy_agent.py     # Create AgentCore Runtime
│   ├── invoke_agent.py     # Test invocations (single or interactive)
│   └── iam_role.json       # CloudFormation IAM role template
├── Dockerfile              # ARM64 container with ADOT entrypoint
└── pyproject.toml          # Dependencies (uv)
```

## Implementation Guide

### Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) package manager
- AWS CLI configured with Bedrock access
- Docker with `buildx` (for ARM64 cross-compilation)
- CloudWatch Transaction Search enabled (one-time)

### Local Development

```bash
cd agentcore-invoice-demo

# Install dependencies
uv sync

# Run interactive mode (no container needed)
uv run python main.py
```

Example prompts:
- `What's the status of INV-001?`
- `Validate invoice INV-003`
- `Show me all overdue invoices`

### Key Implementation Patterns

**1. Strands @tool wraps sub-agents** — Each framework agent is exposed as a Strands tool:

```python
from strands import tool

@tool
def invoice_lookup(query: str) -> str:
    """Look up invoice details by ID or search criteria."""
    agent = _build_langchain_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].content
```

**2. ADOT auto-instrumentation via entrypoint** — The Dockerfile wraps the app with `opentelemetry-instrument`:

```dockerfile
CMD ["uv", "run", "opentelemetry-instrument", "uvicorn", "entrypoint:app", "--host", "0.0.0.0", "--port", "8080"]
```

**3. Traceloop layers LLM-specific spans** — Initialized at startup to auto-instrument LangChain/LangGraph:

```python
from traceloop.sdk import Traceloop
Traceloop.init(app_name="agentcore-invoice-demo")
```

**4. AgentCore service contract** — Two endpoints on port 8080:
- `GET /ping` → 200 (health check)
- `POST /invocations` → agent invocation (receives `sessionId` + `inputText`)

## Testing

### Local Testing (No AWS Required)

```bash
uv run python main.py
```

This starts an interactive REPL that invokes the orchestrator directly. Useful for validating agent routing and tool behavior.

### Remote Testing (After Deployment)

Single prompt:
```bash
python -m deploy.invoke_agent \
  --runtime-arn <RUNTIME_ARN> \
  --prompt "What's the status of INV-001?" \
  --region us-east-1
```

Interactive session:
```bash
python -m deploy.invoke_agent --runtime-arn <RUNTIME_ARN> --region us-east-1
```

### Verifying Traces

1. CloudWatch Console → Application Signals → Traces
2. Filter by service: `agentcore-invoice-demo`
3. Expected trace tree:
   - Root: AgentCore Runtime invocation
   - Child: `orchestrator.invoke` (Strands)
   - Grandchild: `tool.invoice_lookup` or `tool.invoice_validator`
   - Leaf: LangChain/LangGraph LLM calls with timing and token counts

## Deployment

### Step 1: Create IAM Role

```bash
aws cloudformation deploy \
  --template-file deploy/iam_role.json \
  --stack-name agentcore-invoice-demo-role \
  --parameter-overrides AccountId=$(aws sts get-caller-identity --query Account --output text) \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### Step 2: Build & Push Container

```bash
./deploy/build_and_push.sh $(aws sts get-caller-identity --query Account --output text) us-east-1
```

### Step 3: Deploy to AgentCore

```bash
python -m deploy.deploy_agent \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --region us-east-1
```

### Step 4: Enable Tracing

1. AgentCore Console → Select `invoice_demo_agent` → Tracing → Edit → Enable → Save
2. CloudWatch Console → Application Signals → Transaction Search → Enable

### Step 5: Invoke & Verify

```bash
python -m deploy.invoke_agent \
  --runtime-arn <RUNTIME_ARN> \
  --prompt "Validate invoice INV-003" \
  --region us-east-1
```

## Key Constraints

| Constraint | Detail |
|---|---|
| ARM64 required | AgentCore runs on Graviton — build with `--platform linux/arm64` |
| Port 8080 | Hardcoded requirement for the service contract |
| Runtime name pattern | `[a-zA-Z][a-zA-Z0-9_]{0,47}` — no hyphens allowed |
| OTEL entrypoint | Must use `opentelemetry-instrument` as CMD prefix |
| boto3 clients | Control plane: `bedrock-agentcore-control` / Data plane: `bedrock-agentcore` |

## Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| No traces appearing | Transaction Search not enabled | Enable in CloudWatch console |
| ADOT "crashes" | Missing `opentelemetry-instrument` entrypoint | Use it as CMD prefix in Dockerfile |
| LangChain traces missing | OpenLLMetry not initialized | Verify `Traceloop.init()` runs at startup |
| Container fails to start | Not ARM64 | Build with `--platform linux/arm64` |
| `UnknownServiceError` | boto3 too old | `pip install --upgrade boto3 botocore` |
| Runtime name rejected | Contains hyphens | Use underscores instead |

## Cleanup

```bash
# Delete AgentCore Runtime
python -c "
import boto3
client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
client.delete_agent_runtime(agentRuntimeId='<RUNTIME_ID>')
"

# Delete ECR repository
aws ecr delete-repository --repository-name agentcore-invoice-demo --force --region us-east-1

# Delete IAM role
aws cloudformation delete-stack --stack-name agentcore-invoice-demo-role --region us-east-1
```

## References

- [AgentCore Custom Container Deployment](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-custom.html)
- [AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)
- [Strands Agents SDK](https://strandsagents.com/latest/)
- [OpenLLMetry (Traceloop)](https://github.com/traceloop/openllmetry)
- [ADOT Python SDK](https://aws-otel.github.io/docs/getting-started/python-sdk/manual-instr)
