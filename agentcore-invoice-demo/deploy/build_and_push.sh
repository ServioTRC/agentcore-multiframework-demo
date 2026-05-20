#!/usr/bin/env bash
# Build and push the AgentCore Invoice Demo container to ECR.
# Usage: ./deploy/build_and_push.sh <ACCOUNT_ID> [REGION]
set -euo pipefail

ACCOUNT_ID="${1:?Usage: $0 <ACCOUNT_ID> [REGION]}"
REGION="${2:-us-east-1}"
REPO_NAME="agentcore-invoice-demo"
IMAGE_TAG="latest"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"

echo "=== AgentCore Invoice Demo — Build & Push ==="
echo "Account: ${ACCOUNT_ID}"
echo "Region:  ${REGION}"
echo "Image:   ${ECR_URI}:${IMAGE_TAG}"
echo ""

# 1. Create ECR repository (idempotent)
echo "[1/4] Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names "${REPO_NAME}" --region "${REGION}" 2>/dev/null \
  || aws ecr create-repository --repository-name "${REPO_NAME}" --region "${REGION}" \
       --image-scanning-configuration scanOnPush=true

# 2. Authenticate Docker to ECR
echo "[2/4] Logging in to ECR..."
aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# 3. Build ARM64 image
echo "[3/4] Building ARM64 image..."
docker buildx build --platform linux/arm64 \
  -t "${ECR_URI}:${IMAGE_TAG}" \
  --push \
  .

# 4. Verify
echo "[4/4] Verifying image in ECR..."
aws ecr describe-images --repository-name "${REPO_NAME}" --region "${REGION}" \
  --image-ids imageTag="${IMAGE_TAG}" --query 'imageDetails[0].{pushed:imagePushedAt,size:imageSizeInBytes}' --output table

echo ""
echo "=== Done! Image pushed to ${ECR_URI}:${IMAGE_TAG} ==="
echo "Next: python -m deploy.deploy_agent --account-id ${ACCOUNT_ID} --region ${REGION}"
