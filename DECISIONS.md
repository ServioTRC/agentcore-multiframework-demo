# Decisions Log

## Stage 0 — Context & Idea Validation ✅

### Problem Statement
Customer claims AgentCore cannot emit OTEL traces with LangChain/LangGraph agents and that ECS is more mature. Need a working demo to prove feasibility and provide a reference architecture.

### Key Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Main demo uses custom container (not Harness) | Customer is familiar with ECS/containers — meets them where they are |
| 2 | Strands as orchestrator | Lightweight, Python, invokes sub-agents as tools directly |
| 3 | LangChain + LangGraph sub-agents in same runtime | Single project, no isolated runtimes — simpler to build and deploy |
| 4 | AgentCore Harness as side demo | Shows native capabilities with isolated runtimes / agent-to-agent invocation |
| 5 | Invoice processing use case | Matches customer's business domain |
| 6 | Mock data (3 sample invoices) | Keeps focus on runtime/observability, not infra setup |
| 7 | OTEL traces via ADOT → CloudWatch/X-Ray | Directly addresses customer's claim that tracing doesn't work |

### Success Criteria
- ✅ Orchestrator (Strands) calling LangChain and LangGraph sub-agents as tools
- ✅ Full OTEL traces flowing end-to-end (orchestrator → sub-agents)
- ✅ Deployed and running on AgentCore (custom container)
- 🟡 Memory/state visualization (nice-to-have)

### Presentation Angle
"Reference architecture for multi-framework agent orchestration with full observability on AgentCore" — implicitly shows the right way without calling out what customer did wrong.

### Timeline
- Build: Monday–Wednesday (May 18–20)
- Present: Thursday (May 21) checkpoint
