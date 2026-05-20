"""Deploy the invoice demo agent to Amazon Bedrock AgentCore Runtime.

Prerequisites:
  - ECR image pushed (run deploy/build_and_push.sh first)
  - IAM role created (see deploy/iam_role.json)
  - CloudWatch Transaction Search enabled in the account

Usage:
  python -m deploy.deploy_agent --account-id 123456789012 --region us-east-1
"""

import argparse
import sys
import time

import boto3


def deploy_agent(account_id: str, region: str, role_arn: str | None = None):
    """Deploy the agent to AgentCore Runtime."""
    repo_name = "agentcore-invoice-demo"
    image_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repo_name}:latest"
    role_arn = role_arn or f"arn:aws:iam::{account_id}:role/AgentCoreRuntimeRole"

    # Control plane client for creating/managing runtimes
    client = boto3.client("bedrock-agentcore-control", region_name=region)

    print(f"Image URI: {image_uri}")
    print(f"Role ARN:  {role_arn}")
    print("Creating AgentCore Runtime...")

    try:
        response = client.create_agent_runtime(
            agentRuntimeName="invoice_demo_agent",
            description="Invoice processing demo with Strands + LangChain + LangGraph",
            roleArn=role_arn,
            agentRuntimeArtifact={
                "containerConfiguration": {
                    "containerUri": image_uri,
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
    except Exception as e:
        print(f"Error creating agent runtime: {e}", file=sys.stderr)
        sys.exit(1)

    runtime_arn = response["agentRuntimeArn"]
    runtime_id = response["agentRuntimeId"]
    print(f"Agent Runtime ARN: {runtime_arn}")
    print(f"Agent Runtime ID:  {runtime_id}")

    # Poll until READY or FAILED
    print("Waiting for runtime to become READY...")
    for _ in range(30):
        time.sleep(10)
        try:
            status_resp = client.get_agent_runtime(agentRuntimeId=runtime_id)
            status = status_resp.get("status", "UNKNOWN")
            print(f"  Status: {status}")
            if status == "READY":
                break
            if status == "FAILED":
                print(f"  Failure reason: {status_resp.get('failureReason', 'unknown')}", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"  Error polling status: {e}")
    else:
        print("Timeout waiting for runtime (5 min). Check console.", file=sys.stderr)
        sys.exit(1)

    print("\n=== Deployment Complete ===")
    print(f"Runtime ARN: {runtime_arn}")
    print(f"\nNext steps:")
    print(f"  1. Enable tracing: AgentCore Console → Agent Runtime → Tracing → Enable")
    print(f"  2. Test invocation:")
    print(f"     python -m deploy.invoke_agent --runtime-id {runtime_id} --region {region}")
    return runtime_arn


def main():
    parser = argparse.ArgumentParser(description="Deploy invoice demo to AgentCore")
    parser.add_argument("--account-id", required=True, help="AWS Account ID")
    parser.add_argument("--region", default="us-east-1", help="AWS Region")
    parser.add_argument("--role-arn", help="IAM Role ARN (default: AgentCoreRuntimeRole)")
    args = parser.parse_args()
    deploy_agent(args.account_id, args.region, args.role_arn)


if __name__ == "__main__":
    main()
