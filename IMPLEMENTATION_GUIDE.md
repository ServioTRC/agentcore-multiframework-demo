# Implementation Guide: AgentCore Invoice Processing Demo

## Prerequisites

- AWS account with Bedrock AgentCore access
- Docker with buildx (ARM64 cross-compilation)
- Python 3.11+
- `uv` package manager
- AWS CLI configured
- CloudWatch Transaction Search enabled (one-time)

---

## Phase 1: Project Setup (Day 1 — Monday morning)

### 1.1 Initialize Project

```bash
mkdir agentcore-invoice-demo && cd agentcore-invoice-demo
uv init --python 3.11
```

### 1.2 Add Dependencies

```bash
uv add \
  fastapi \
  'uvicorn[standard]' \
  pydantic \
  strands-agents \
  strands-agents-tools \
  langchain \
  langchain-aws \
  langgraph \
  boto3 \
  aws-opentelemetry-distro \
  opentelemetry-instrumentation-langchain \
  traceloop-sdk
```

### 1.3 Project Structure

```
agentcore-invoice-demo/
├── agent.py                  # FastAPI server (AgentCore contract)
├── orchestrator.py           # Strands orchestrator agent
├── tools/
│   ├── __init__.py
│   ├── invoice_lookup.py     # LangChain sub-agent (tool)
│   └── invoice_validator.py  # LangGraph sub-agent (tool)
├── data/
│   └── mock_invoices.py      # Mock invoice data
├── observability.py          # OTEL/ADOT configuration
├── Dockerfile
├── pyproject.toml
└── deploy/
    ├── deploy_agent.py
    └── invoke_agent.py
```

---

## Phase 2: Build the Agents (Day 1 — Monday afternoon + Day 2)

### 2.1 Mock Data (`data/mock_invoices.py`)

Define 3 sample invoices as Python dicts. Include fields: invoice_id, vendor, amount, status, due_date, line_items, po_number (intentionally missing on INV-003 for validation demo).

### 2.2 LangChain Sub-Agent — Invoice Lookup (`tools/invoice_lookup.py`)

**What it does:** Simple retrieval — given an invoice ID or query, returns invoice details/status.

**Implementation approach:**
1. Create a LangChain agent with a custom tool that searches mock_invoices
2. Use `ChatBedrock` (Claude or Nova) as the LLM
3. The tool returns invoice data; the LLM formats a natural language response
4. Wrap the entire LangChain agent invocation as a Strands `@tool`

**Key pattern:**
```python
from strands import tool

@tool
def invoice_lookup(query: str) -> str:
    """Look up invoice details by ID or search criteria. Use for status checks and invoice retrieval."""
    # LangChain agent invocation here
    ...
```

### 2.3 LangGraph Sub-Agent — Invoice Validator (`tools/invoice_validator.py`)

**What it does:** Multi-step validation workflow:
- Node 1: Extract key fields from invoice
- Node 2: Validate against business rules (amount thresholds, required fields)
- Node 3: Flag discrepancies and generate report

**Implementation approach:**
1. Define a LangGraph `StateGraph` with 3 nodes
2. Use `ChatBedrock` as the LLM for reasoning at each node
3. State carries: invoice_data, extracted_fields, validation_results, final_report
4. Wrap the graph invocation as a Strands `@tool`

**Key pattern:**
```python
from strands import tool

@tool
def invoice_validator(invoice_id: str) -> str:
    """Validate an invoice against business rules. Checks amount thresholds, required fields, and payment terms."""
    # LangGraph StateGraph invocation here
    ...
```

### 2.4 Strands Orchestrator (`orchestrator.py`)

**What it does:** Receives user prompts, decides which tool to call.

**Implementation approach:**
1. Create a Strands `Agent` with both tools registered
2. System prompt instructs it to route lookup queries to `invoice_lookup` and validation requests to `invoice_validator`
3. The agent handles multi-turn conversation naturally

**Key pattern:**
```python
from strands import Agent
from tools.invoice_lookup import invoice_lookup
from tools.invoice_validator import invoice_validator

agent = Agent(
    tools=[invoice_lookup, invoice_validator],
    system_prompt="You are an invoice processing assistant..."
)
```

### 2.5 FastAPI Server (`agent.py`)

**What it does:** Implements AgentCore's service contract.

**Endpoints:**
- `POST /invocations` — receives prompt, invokes orchestrator, returns response
- `GET /ping` — health check

Follow the exact pattern from AWS docs (see SOLUTION_BRIEF.md references).

---

## Phase 3: Observability Setup (Day 2 — Tuesday)

### 3.1 ADOT Configuration (`observability.py`)

**Critical steps:**
1. The `aws-opentelemetry-distro` package handles most configuration automatically when launched with `opentelemetry-instrument`
2. For LangChain traces, initialize OpenLLMetry/Traceloop SDK at startup:

```python
from traceloop.sdk import Traceloop
Traceloop.init(app_name="invoice-demo")
```

3. This auto-instruments all LangChain and LangGraph calls with OTEL spans

### 3.2 Dockerfile Entrypoint

**Critical:** Use `opentelemetry-instrument` as the entrypoint to enable auto-instrumentation:

```dockerfile
CMD ["opentelemetry-instrument", "uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8080"]
```

This is the key pattern the customer likely missed — ADOT auto-instrumentation must wrap the application process.

### 3.3 Enable CloudWatch Transaction Search (One-time)

1. Open CloudWatch console → Application Signals (APM) → Transaction Search
2. Choose "Enable Transaction Search"
3. Select checkbox to ingest spans as structured logs
4. Save

### 3.4 Enable Tracing on AgentCore Runtime

After deployment:
1. Open AgentCore console → Agent Runtime
2. Select your agent → Tracing pane → Edit → Enable → Save

### 3.5 What Traces Will Show

Once running, CloudWatch GenAI Observability will display:
- **Root span:** AgentCore Runtime invocation
- **Child span:** Strands orchestrator reasoning
- **Child span:** Tool selection (invoice_lookup or invoice_validator)
- **Grandchild spans:** LangChain/LangGraph LLM calls, tool executions
- **Timing, tokens, model calls** all visible per span

This is the money shot for the demo — a full trace tree proving everything works.

---

## Phase 4: Containerize & Deploy (Day 3 — Wednesday)

### 4.1 Dockerfile

```dockerfile
FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache
COPY . .
EXPOSE 8080

CMD ["uv", "run", "opentelemetry-instrument", "uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 4.2 Build & Push to ECR

```bash
# Create ECR repo
aws ecr create-repository --repository-name agentcore-invoice-demo --region us-east-1

# Login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build ARM64 and push
docker buildx build --platform linux/arm64 \
  -t <account-id>.dkr.ecr.us-east-1.amazonaws.com/agentcore-invoice-demo:latest \
  --push .
```

### 4.3 Deploy to AgentCore Runtime

```python
import boto3

client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')

response = client.create_agent_runtime(
    agentRuntimeName='invoice-demo-agent',
    agentRuntimeArtifact={
        'containerConfiguration': {
            'containerUri': '<account-id>.dkr.ecr.us-east-1.amazonaws.com/agentcore-invoice-demo:latest'
        }
    },
    networkConfiguration={"networkMode": "PUBLIC"},
    roleArn='arn:aws:iam::<account-id>:role/AgentCoreRuntimeRole',
    lifecycleConfiguration={
        'idleRuntimeSessionTimeout': 300,
        'maxLifetime': 1800
    },
)
```

### 4.4 Invoke & Verify

```python
import boto3, json

client = boto3.client('bedrock-agentcore', region_name='us-east-1')

response = client.invoke_agent_runtime(
    agentRuntimeArn='<agent-runtime-arn>',
    runtimeSessionId='invoice-demo-session-123456789abcdef',
    payload=json.dumps({"input": {"prompt": "What's the status of invoice INV-001?"}}),
    qualifier="DEFAULT"
)

print(json.loads(response['response'].read()))
```

---

## Phase 5: Demo Script (Thursday presentation)

### Demo Flow

1. **Show the code** — "Here's a single project with Strands orchestrator, LangChain agent, and LangGraph agent"
2. **Show the Dockerfile** — "Standard container, same workflow as ECS"
3. **Deploy live** (or show pre-deployed) — "One API call to deploy"
4. **Invoke: Lookup** — "What's the status of INV-002?" → Shows LangChain agent responding
5. **Invoke: Validation** — "Validate INV-003" → Shows LangGraph multi-step flow
6. **Show traces in CloudWatch** — Full trace tree with timing, tokens, spans across all frameworks
7. **Side demo (if time):** Show same thing on AgentCore Harness with A2A protocol

### Key Talking Points

- "Custom containers give you the same flexibility as ECS — bring your Dockerfile, your frameworks, your libraries"
- "ADOT auto-instrumentation works out of the box — one line in your Dockerfile"
- "LangChain, LangGraph, Strands all emit traces correctly — the key is using `opentelemetry-instrument` as your entrypoint"
- "AgentCore adds session isolation, auto-scaling, and built-in observability that you'd have to build yourself on ECS"

---

## IAM Role Requirements

The `AgentCoreRuntimeRole` needs:
- `bedrock:InvokeModel` — for LLM calls
- `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage` — for pulling container
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` — for CloudWatch
- `xray:PutTraceSegments`, `xray:PutTelemetryRecords` — for traces

---

## Troubleshooting (Common Issues)

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| No traces appearing | Transaction Search not enabled | Enable in CloudWatch console |
| ADOT "crashes" | Missing `opentelemetry-instrument` entrypoint | Use it as CMD prefix in Dockerfile |
| LangChain traces missing | OpenLLMetry not initialized | Add `Traceloop.init()` at startup |
| Container fails to start | Not ARM64 | Build with `--platform linux/arm64` |
| Invocation timeout | Agent takes too long | Increase `maxLifetime` in lifecycle config |

---

## References

- [AgentCore Custom Container Deployment](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-custom.html)
- [AgentCore Observability Configuration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)
- [AgentCore Observability Getting Started](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-get-started.html)
- [Strands Agents SDK — Tools](https://strandsagents.com/docs/user-guide/concepts/tools/)
- [ADOT Python Manual Instrumentation](https://aws-otel.github.io/docs/getting-started/python-sdk/manual-instr)
- [OpenLLMetry (Traceloop)](https://github.com/traceloop/openllmetry)
- [AgentCore A2A Protocol](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html)
