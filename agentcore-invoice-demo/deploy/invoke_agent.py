"""Invoke the deployed AgentCore invoice demo agent for testing.

Usage:
  python -m deploy.invoke_agent --runtime-arn <arn> --prompt "What's the status of INV-001?"
  python -m deploy.invoke_agent --runtime-arn <arn>  # interactive mode
"""

import argparse
import json
import uuid

import boto3


def invoke_agent(runtime_arn: str, prompt: str, region: str, session_id: str | None = None):
    """Send a prompt to the deployed agent and return the response."""
    client = boto3.client("bedrock-agent-runtime", region_name=region)
    session_id = session_id or f"session-{uuid.uuid4().hex[:16]}"

    response = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=session_id,
        payload=json.dumps({"inputText": prompt}),
        qualifier="LIVE",
    )

    body = json.loads(response["response"].read())
    return body.get("outputText", body)


def interactive_mode(runtime_arn: str, region: str):
    """Run an interactive session against the deployed agent."""
    session_id = f"session-{uuid.uuid4().hex[:16]}"
    print("AgentCore Invoice Demo — Interactive Mode")
    print(f"Session: {session_id}")
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
            result = invoke_agent(runtime_arn, user_input, region, session_id)
            print(f"\n{result}")
        except Exception as e:
            print(f"\nError: {e}")


def main():
    parser = argparse.ArgumentParser(description="Invoke the deployed AgentCore agent")
    parser.add_argument("--runtime-arn", required=True, help="Agent Runtime ARN")
    parser.add_argument("--region", default="us-east-1", help="AWS Region")
    parser.add_argument("--prompt", help="Single prompt (omit for interactive mode)")
    parser.add_argument("--session-id", help="Session ID (auto-generated if omitted)")
    args = parser.parse_args()

    if args.prompt:
        result = invoke_agent(args.runtime_arn, args.prompt, args.region, args.session_id)
        print(result)
    else:
        interactive_mode(args.runtime_arn, args.region)


if __name__ == "__main__":
    main()
