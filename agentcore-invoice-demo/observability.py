"""Observability configuration for ADOT + OpenLLMetry on AgentCore Runtime.

Architecture:
- ADOT (via `opentelemetry-instrument` entrypoint) auto-instruments FastAPI, boto3, botocore.
- Traceloop SDK auto-instruments LangChain and LangGraph calls.
- Both share the global TracerProvider — spans from LangChain appear as children of FastAPI request spans.
- AgentCore injects OTEL env vars at runtime (OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME, etc.)
  so we do NOT hardcode them here.

Usage:
    Call `init_observability()` at application startup before any LLM invocations.
    The `get_tracer()` helper provides a tracer for manual spans (e.g., Strands tool calls).
"""

import logging
import os

from opentelemetry import trace

logger = logging.getLogger(__name__)

_SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "agentcore-invoice-demo")


def init_observability() -> None:
    """Initialize OpenLLMetry for LangChain/LangGraph auto-instrumentation.

    ADOT handles FastAPI/boto3 via the `opentelemetry-instrument` entrypoint.
    This function layers Traceloop on top to capture LLM-specific spans.
    """
    try:
        from traceloop.sdk import Traceloop

        Traceloop.init(
            app_name=_SERVICE_NAME,
            disable_batch=False,
        )
        logger.info("OpenLLMetry (Traceloop) initialized for LangChain/LangGraph tracing")
    except ImportError:
        logger.warning("traceloop-sdk not installed — LLM tracing disabled")
    except Exception as e:
        logger.warning("Traceloop init failed (non-fatal): %s", e)


def get_tracer(module_name: str = "agentcore-invoice-demo") -> trace.Tracer:
    """Return an OTEL tracer for creating manual spans (e.g., Strands tool calls)."""
    return trace.get_tracer(module_name)
