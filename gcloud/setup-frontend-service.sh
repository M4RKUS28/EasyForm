#!/bin/bash

# EasyForm Frontend Service Setup
# This script sets up the frontend Cloud Run service for EasyForm

# Project configuration
PROJECT_ID="cloud-run-hackathon-475303"
REGION="us-central1"
SERVICE_NAME="easyform-frontend"

# 1. Create Artifact Registry repository for frontend images
echo "Creating Artifact Registry repository for frontend..."
gcloud artifacts repositories create easyform-frontend-repo \
  --repository-format=docker \
  --location=$REGION \
  --project=$PROJECT_ID \
  --description="Docker repository for EasyForm frontend images"

# 2. Create Network Endpoint Group (NEG) for frontend service
echo "Creating serverless NEG for frontend..."
gcloud compute network-endpoint-groups create easyform-frontend-neg \
  --region=$REGION \
  --network-endpoint-type=serverless \
  --cloud-run-service=$SERVICE_NAME

# 3. Create backend service with CDN enabled for frontend
echo "Creating frontend backend service with CDN..."
gcloud compute backend-services create easyform-frontend-service \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --protocol=HTTP \
  --enable-cdn

# 4. Attach NEG to frontend backend service
echo "Attaching NEG to frontend backend service..."
gcloud compute backend-services add-backend easyform-frontend-service \
  --global \
  --network-endpoint-group=easyform-frontend-neg \
  --network-endpoint-group-region=$REGION

echo "Frontend service setup complete!"
echo "Next steps:"
echo "1. Deploy the frontend service using GitHub Actions or manually"
echo "2. Run setup-load-balancer.sh to configure the load balancer"
