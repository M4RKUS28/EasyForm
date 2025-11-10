#!/bin/bash

# EasyForm Backend Service Setup
# This script sets up the backend Cloud Run service for EasyForm

# Project configuration
PROJECT_ID="cloud-run-hackathon-475303"
REGION="us-central1"
SERVICE_NAME="easyform-backend"

# 1. Create Artifact Registry repository for backend images
echo "Creating Artifact Registry repository for backend..."
gcloud artifacts repositories create easyform-backend-repo \
  --repository-format=docker \
  --location=$REGION \
  --project=$PROJECT_ID \
  --description="Docker repository for EasyForm backend images"

# 2. Create Network Endpoint Group (NEG) for backend service
echo "Creating serverless NEG for backend..."
gcloud compute network-endpoint-groups create easyform-backend-neg \
  --region=$REGION \
  --network-endpoint-type=serverless \
  --cloud-run-service=$SERVICE_NAME

# 3. Create backend service for Cloud Run
echo "Creating backend service..."
gcloud compute backend-services create easyform-backend-service \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --protocol=HTTP

# 4. Attach NEG to backend service
echo "Attaching NEG to backend service..."
gcloud compute backend-services add-backend easyform-backend-service \
  --global \
  --network-endpoint-group=easyform-backend-neg \
  --network-endpoint-group-region=$REGION

echo "Backend service setup complete!"
echo "Next steps:"
echo "1. Deploy the backend service using GitHub Actions or manually"
echo "2. Run setup-frontend-service.sh to set up the frontend"
echo "3. Run setup-load-balancer.sh to configure the load balancer"
