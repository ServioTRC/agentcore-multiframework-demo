import uuid

session_id = f"{uuid.uuid4()}"

print(session_id)

import boto3
client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
resp = client.get_agent_runtime(agentRuntimeId='invoice_demo_agent-tADvr5A4tk')
print(resp['agentRuntimeArn'])