# Solution Brief: AgentCore Invoice Processing Demo

## Problem Statement

Customer claims that:
1. AgentCore Runtime cannot emit OTEL traces when running LangChain/LangGraph agents
2. ADOT library "crashes" with LangChain and LangGraph agents
3. ECS is a more mature and better deployment option

**Goal:** Prove all three claims wrong with a working reference architecture that the customer can adopt directly.

---

## Proposed Architecture

### Main Demo: Custom Container on AgentCore Runtime

A single custom Docker container deployed on AgentCore Runtime containing:

| Component | Framework | Role |
|-----------|-----------|------|
| Orchestrator | Strands Agents SDK | Routes user requests, invokes sub-agents as tools |
| Sub-agent 1 | LangChain | Invoice Lookup — retrieves invoice status/details |
| Sub-agent 2 | LangGraph | Invoice Validation — multi-step: extract → validate → flag discrepancies |
| Observability | ADOT SDK + OpenLLMetry | Full OTEL traces flowing to CloudWatch GenAI Observability |

### Side Demo: AgentCore Harness (Native)

Same logic but deployed using AgentCore Harness with isolated runtimes and agent-to-agent (A2A) invocation — showing the "fully native" path.

---

## Use Case: Invoice Processing Assistant

**User prompt examples:**
- "What's the status of invoice INV-001?"
- "Validate invoice INV-003 against our payment rules"
- "Show me all overdue invoices"

**Mock Data (3 invoices):**

| Invoice ID | Vendor | Amount | Status | Due Date | Notes |
|------------|--------|--------|--------|----------|-------|
| INV-001 | Acme Corp | $12,500.00 | Paid | 2026-04-15 | Paid on time |
| INV-002 | GlobalTech | $8,750.50 | Pending | 2026-05-20 | Awaiting approval |
| INV-003 | FastShip LLC | $45,000.00 | Overdue | 2026-04-01 | Amount exceeds $25K threshold, missing PO number |

---

## AWS Services & Tools

| Service | Purpose | Verified |
|---------|---------|----------|
| Amazon Bedrock AgentCore Runtime | Serverless agent hosting (custom container) | ✅ |
| Amazon Bedrock (Claude/Nova) | LLM for agent reasoning | ✅ |
| AWS Distro for OpenTelemetry (ADOT) | Trace instrumentation | ✅ |
| Amazon CloudWatch GenAI Observability | Trace visualization, dashboards | ✅ |
| Amazon ECR | Container image registry | ✅ |
| OpenLLMetry (Traceloop) | LangChain/LangGraph auto-instrumentation | ✅ Supported by AgentCore |

---

## Key Benefits Demonstrated

1. **Framework Agnostic Runtime** — Strands, LangChain, and LangGraph coexist in one container without conflicts
2. **OTEL Works** — Full distributed traces from orchestrator through sub-agents, visible in CloudWatch
3. **Custom Container = ECS-like DX** — Same Dockerfile workflow they already know, but with AgentCore's managed scaling, session isolation, and built-in observability
4. **Zero Infrastructure Management** — No ECS clusters, task definitions, ALBs, or auto-scaling policies to configure
5. **Built-in Session Management** — AgentCore handles session isolation automatically

---

## Constraints & Considerations

- **ARM64 required** — AgentCore Runtime requires linux/arm64 containers
- **Service contract** — Must expose `/invocations` (POST) and `/ping` (GET) on port 8080
- **ADOT auto-instrumentation** — Use `opentelemetry-instrument` as the container entrypoint
- **CloudWatch Transaction Search** — Must be enabled (one-time setup) before traces appear
- **LangChain OTEL** — Use `opentelemetry-instrumentation-langchain` (OpenLLMetry) for auto-instrumentation
- **Timeline** — Build Mon–Wed (May 18–20), present Thu (May 21)

---

## Presentation Angle

> "Here's a reference architecture for deploying multi-framework agents on AgentCore with full observability. This pattern works with LangChain, LangGraph, Strands, or any Python agent framework — in a single container with the same Dockerfile workflow you'd use on ECS, but without managing the infrastructure."

The demo implicitly addresses their concerns without calling them out:
- Traces flowing = "it doesn't crash"
- Custom container = "it's as flexible as ECS"
- Mixed frameworks = "no vendor lock-in"
