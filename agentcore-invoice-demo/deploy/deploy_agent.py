"""Deploy the invoice demo agent to Amazon Bedrock AgentCore Runtime.

Prerequisites:
  - ECR repository created and image pushed (see Dockerfile)
  - IAM role with Bedrock, ECR, X-Ray, and CloudWatch permissions
  - CloudWatch Transaction Search enabled in the account

Usage:
  python -m deploy.deploy_agent --account-id 123456789012 --region us-east-1
"""

import argparse
import json
import sys
import time

import boto3


def get_or_create_ecr_repo(ecr_client, repo_name: str) -> str:
    """Ensure ECR repository exists and return its URI."""
    try:
        resp = ecr_client.describe_repositories(repositoryNames=[repo_name])
        return resp["repositories"][0]["repositoryUri"]
    except ecr_client.exceptions.RepositoryNotFoundException:
        resp = ecr_client.create_repository(repositoryName=repo_name)
        return resp["repository"]["repositoryUri"]


def deploy_agent(account_id: str, region: str, role_arn: str | None = None):
    """Deploy the agent to AgentCore Runtime with observability enabled."""
    repo_name = "agentcore-invoice-demo"
    image_uri = f"{account_id}.dkr.ecr.{region}.amazonaws.com/{repo_name}:latest"
    role_arn = role_arn or f"arn:aws:iam::{account_id}:role/AgentCoreRuntimeRole"

    client = boto3.client("bedrock-agent-runtime", region_name=region)
    ecr_client = boto3.client("ecr", region_name=region)

    # Ensure ECR repo exists
    get_or_create_ecr_repo(ecr_client, repo_name)
    print(f"ECR image URI: {image_uri}")

    # Create AgentCore Runtime
    print("Creating AgentCore Runtime...")
    try:
        response = client.create_agent_runtime(
            agentRuntimeName="invoice-demo-agent",
            agentRuntimeArtifact={
                "containerConfiguration": {
                    "containerUri": image_uri,
                }
            },
            networkConfiguration={"networkMode": "PUBLIC"},
            roleArn=role_arn,
            protocolConfiguration={"serverProtocol": "HTTP"},
            environmentVariables={
                "OTEL_SERVICE_NAME": "agentcore-invoice-demo",
            },
        )
    except Exception as e:
        print(f"Error creating agent runtime: {e}", file=sys.stderr)
        sys.exit(1)

    runtime_arn = response["agentRuntimeArn"]
    runtime_id = response["agentRuntimeId"]
    print(f"Agent Runtime ARN: {runtime_arn}")
    print(f"Agent Runtime ID:  {runtime_id}")

    # Wait for runtime to become active
    print("Waiting for runtime to become ACTIVE...")
    for _ in range(30):
        time.sleep(10)
        status_resp = client.get_agent_runtime(agentRuntimeId=runtime_id)
        status = status_resp.get("status", "UNKNOWN")
        print(f"  Status: {status}")
        if status == "ACTIVE":
            break
    else:
        print("Timeout waiting for runtime to become active.", file=sys.stderr)

    print("\n--- Deployment Complete ---")
    print(f"Runtime ARN: {runtime_arn}")
    print(f"\nNext steps:")
    print(f"  1. Enable tracing: AgentCore Console → Agent Runtime → Tracing → Enable")
    print(f"  2. Test: python -m deploy.invoke_agent --runtime-arn {runtime_arn}")
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
