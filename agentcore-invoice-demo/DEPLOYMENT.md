# Deployment Know-How: AgentCore Invoice Demo

Lessons learned and constraints discovered while deploying to Amazon Bedrock AgentCore Runtime in `us-east-1`.

---

## AgentCore API Constraints

### Agent Runtime Name
- **Pattern:** `[a-zA-Z][a-zA-Z0-9_]{0,47}`
- No hyphens (`-`) allowed — use underscores (`_`)
- Must start with a letter
- Max 48 characters

```python
# ❌ Wrong
agentRuntimeName="invoice-demo-agent"

# ✅ Correct
agentRuntimeName="invoice_demo_agent"
```

### Authorizer Configuration
- `authorizerConfiguration` is optional — omit it entirely if you don't need a custom JWT authorizer
- The only valid key is `customJWTAuthorizer` (not `customAuthorizerConfig`)

```python
# ❌ Wrong
authorizerConfiguration={"customAuthorizerConfig": {"type": "NONE"}}

# ✅ Correct — just don't include it
# (omit authorizerConfiguration entirely)
```

### boto3 Client Names
| Operation | Client Name |
|-----------|-------------|
| Create/manage runtimes | `bedrock-agentcore-control` |
| Invoke runtimes | `bedrock-agentcore` |

### Required Parameters for `create_agent_runtime`
```python
client = boto3.client("bedrock-agentcore-control", region_name="us-east-1")

response = client.create_agent_runtime(
    agentRuntimeName="invoice_demo_agent",
    description="Invoice processing demo",
    roleArn="arn:aws:iam::<ACCOUNT_ID>:role/AgentCoreRuntimeRole",
    agentRuntimeArtifact={
        "containerConfiguration": {
            "containerUri": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/agentcore-invoice-demo:latest",
        }
    },
    networkConfiguration={"networkMode": "PUBLIC"},
    protocolConfiguration={"serverProtocol": "HTTP"},
    environmentVariables={
        "OTEL_SERVICE_NAME": "agentcore-invoice-demo",
        "OTEL_PYTHON_DISTRO": "aws_distro",
        "OTEL_PYTHON_CONFIGURATOR": "aws_configurator",
    },
)
```

---

## Docker / ECR Constraints

### Docker Desktop Must Be Running
If you get:
```
ERROR: failed to connect to the docker API at unix:///...docker.sock
```
Start Docker Desktop:
```bash
open -a Docker
# Wait for daemon, then verify:
docker info >/dev/null 2>&1 && echo "Ready" || echo "Not yet"
```

### ARM64 Required
AgentCore runs on Graviton (ARM64). Build with:
```bash
docker buildx build --platform linux/arm64 -t <ECR_URI>:latest --push .
```

### ECR Login
```bash
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
```

---

## Container Service Contract

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ping` | GET | Health check — must return 200 |
| `/invocations` | POST | Agent invocation — receives JSON payload |

- **Port:** 8080 (hardcoded requirement)
- **Startup grace:** ~120 seconds before health checks fail

---

## IAM Role

- **Trust principal:** `bedrock-agentcore.amazonaws.com`
- **Required permissions:**
  - `bedrock:InvokeModel` / `bedrock:InvokeModelWithResponseStream`
  - `ecr:GetDownloadUrlForLayer` / `ecr:BatchGetImage` / `ecr:GetAuthorizationToken`
  - `logs:CreateLogGroup` / `logs:CreateLogStream` / `logs:PutLogEvents`
  - `xray:PutTraceSegments` / `xray:PutTelemetryRecords`

Deploy with CloudFormation:
```bash
aws cloudformation deploy \
  --template-file deploy/iam_role.json \
  --stack-name agentcore-invoice-demo-role \
  --parameter-overrides AccountId=<ACCOUNT_ID> \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

---

## Observability Setup

### OTEL Auto-Instrumentation
The Dockerfile entrypoint must use `opentelemetry-instrument` to wrap the app:
```dockerfile
CMD ["uv", "run", "opentelemetry-instrument", "uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Enable CloudWatch Transaction Search (one-time)
1. CloudWatch Console → Application Signals → Transaction Search
2. Enable → Check "Ingest spans as structured logs" → Save

### Enable Tracing on the Runtime (after deploy)
1. AgentCore Console → Select runtime → Tracing → Edit → Enable → Save

---

## boto3 Version

If you get `UnknownServiceError`, upgrade boto3:
```bash
pip install --upgrade boto3 botocore
```

Verify AgentCore is available:
```python
import botocore
print([s for s in botocore.session.Session().get_available_services() if 'agentcore' in s])
```

---

## Full Deployment Sequence

```bash
# 1. Create IAM role
aws cloudformation deploy --template-file deploy/iam_role.json \
  --stack-name agentcore-invoice-demo-role \
  --parameter-overrides AccountId=449828813699 \
  --capabilities CAPABILITY_NAMED_IAM --region us-east-1

# 2. Build & push container
./deploy/build_and_push.sh 449828813699 us-east-1

# 3. Deploy to AgentCore
python3 -m deploy.deploy_agent --account-id 449828813699 --region us-east-1

# 4. Test invocation
python3 -m deploy.invoke_agent --runtime-id <RUNTIME_ID> --prompt "What's the status of INV-001?"
```

python3 -m deploy.invoke_agent \
    --runtime-arn arn:aws:bedrock-agentcore:us-east-1:449828813699:runtime/invoice_demo_agent-tADvr5A4tk \
    --prompt "What's the status of INV-001?" --region "us-east-1"