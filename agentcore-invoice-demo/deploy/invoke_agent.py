"""Invoke the deployed AgentCore invoice demo agent for testing.

Usage:
  python -m deploy.invoke_agent --runtime-id <id> --prompt "What's the status of INV-001?"
  python -m deploy.invoke_agent --runtime-id <id>  # interactive mode
"""

import argparse
import json
import uuid

import boto3


def invoke_agent(runtime_id: str, prompt: str, region: str, session_id: str | None = None):
    """Send a prompt to the deployed agent and return the response."""
    # Data plane client for invoking runtimes
    client = boto3.client("bedrock-agentcore", region_name=region)
    session_id = session_id or f"session-{uuid.uuid4().hex[:16]}"

    payload = json.dumps({"sessionId": session_id, "inputText": prompt}).encode("utf-8")

    response = client.invoke_agent_runtime(
        agentRuntimeId=runtime_id,
        payload=payload,
        contentType="application/json",
        accept="application/json",
    )

    body = json.loads(response["body"].read())
    return body.get("outputText", json.dumps(body, indent=2))


def interactive_mode(runtime_id: str, region: str):
    """Run an interactive session against the deployed agent."""
    session_id = f"session-{uuid.uuid4().hex[:16]}"
    print("AgentCore Invoice Demo — Interactive Mode")
    print(f"Runtime ID: {runtime_id}")
    print(f"Session:    {session_id}")
    print("=" * 50)
    print("Try: 'What's the status of INV-001?'")
    print("     'Validate invoice INV-003'")
    print("     'Show me all overdue invoices'")
    print("=" * 50)

    while True:
        user_input = input("\n> ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue
        try:
            result = invoke_agent(runtime_id, user_input, region, session_id)
            print(f"\n{result}")
        except Exception as e:
            print(f"\nError: {e}")


def main():
    parser = argparse.ArgumentParser(description="Invoke the deployed AgentCore agent")
    parser.add_argument("--runtime-id", required=True, help="Agent Runtime ID")
    parser.add_argument("--region", default="us-east-1", help="AWS Region")
    parser.add_argument("--prompt", help="Single prompt (omit for interactive mode)")
    parser.add_argument("--session-id", help="Session ID (auto-generated if omitted)")
    args = parser.parse_args()

    if args.prompt:
        result = invoke_agent(args.runtime_id, args.prompt, args.region, args.session_id)
        print(result)
    else:
        interactive_mode(args.runtime_id, args.region)


if __name__ == "__main__":
    main()
