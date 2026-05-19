"""FastAPI server implementing the AgentCore Runtime service contract."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry import trace

from observability import init_observability, get_tracer
from orchestrator import create_orchestrator

# Initialize OpenLLMetry (LangChain/LangGraph tracing) before any LLM calls.
# ADOT auto-instruments FastAPI/boto3 via the opentelemetry-instrument entrypoint.
init_observability()

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)

app = FastAPI(title="AgentCore Invoice Demo")
orchestrator = create_orchestrator()


@app.get("/ping")
async def ping():
    """Health check endpoint required by AgentCore Runtime."""
    return JSONResponse(status_code=200, content={})


@app.post("/invocations")
async def invocations(request: Request):
    """Main invocation endpoint required by AgentCore Runtime."""
    body = await request.json()
    session_id = body.get("sessionId", "default-session")
    input_text = body.get("inputText", "")

    if not input_text:
        return JSONResponse(status_code=400, content={"error": "inputText is required"})

    with tracer.start_as_current_span("orchestrator.invoke") as span:
        span.set_attribute("session.id", session_id)
        span.set_attribute("input.text", input_text[:200])
        try:
            result = orchestrator(input_text)
            output = str(result)
            span.set_attribute("output.length", len(output))
            span.set_status(trace.StatusCode.OK)
        except Exception as e:
            span.set_status(trace.StatusCode.ERROR, str(e))
            span.record_exception(e)
            logger.exception("Orchestrator invocation failed")
            return JSONResponse(status_code=500, content={"error": "Internal error"})

    return JSONResponse(content={"sessionId": session_id, "outputText": output})
