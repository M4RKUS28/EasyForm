# EasyForm Cloud Run Setup Protocol

This document records the setup of EasyForm on Google Cloud Platform using the existing Piatto infrastructure.

## Context

- **Project:** `cloud-run-hackathon-475303` (shared with Piatto)
- **Region:** `us-central1`
- **Backend Service:** `easyform-backend`
- **Frontend Service:** `easyform-frontend`
- **Domain:** `easyform-ai.com`, `www.easyform-ai.com`
- **Database:** Shared MySQL instance at `10.73.16.3:3306`, separate database `easyform`
- **VPC Connector:** `svpc-uscentral1` (shared with Piatto)

## Architecture Overview

```
                    [Load Balancer]
                          |
        +-----------------+------------------+
        |                                    |
   [easyform-ai.com]                 [piatto-cooks.com]
        |                                    |
        +----------+                         +----------+
        |          |                         |          |
    /api/*     default                   /api/*    /assets/*
        |          |                         |          |
   [Backend]  [Frontend]                [Backend]   [Bucket]
   Cloud Run  Cloud Run                 Cloud Run   Cloud Storage
        |          |                         |
        +----------+-------------------------+
                   |
            [MySQL Database]
            10.73.16.3:3306
              - piatto (DB)
              - easyform (DB)
```

## Differences from Piatto Setup

1. **No Cloud Storage Bucket:** EasyForm serves ALL assets (including /assets/*) through the Cloud Run frontend service
2. **Simplified routing:** Only two routes: /api/* → backend, everything else → frontend
3. **Shared infrastructure:** Uses same load balancer, SSL setup, and MySQL instance as Piatto
4. **Separate Artifact Registry repos:** `easyform-backend-repo` and `easyform-frontend-repo`

## Prerequisites

1. Active GCloud project `cloud-run-hackathon-475303`
2. VPC Connector `svpc-uscentral1` already set up
3. MySQL instance at `10.73.16.3:3306` with database `easyform` created
4. GitHub Secrets configured:
   - `GCP_SA_KEY`: Service account key with permissions for Artifact Registry and Cloud Run
   - `DB_PASSWORD`: MySQL password for backend user
   - `SECRET_KEY`: Application secret key
   - `GOOGLE_API_KEY`: Google API key (shared with Piatto)

## Setup Steps

### 1. Create Artifact Registry Repositories

Set the active project:

```bash
gcloud config set project cloud-run-hackathon-475303
```

Create repositories for backend and frontend:

```bash
# Backend repository
gcloud artifacts repositories create easyform-backend-repo \
  --repository-format=docker \
  --location=us-central1 \
  --project=cloud-run-hackathon-475303 \
  --description="Docker repository for EasyForm backend images"

# Frontend repository
gcloud artifacts repositories create easyform-frontend-repo \
  --repository-format=docker \
  --location=us-central1 \
  --project=cloud-run-hackathon-475303 \
  --description="Docker repository for EasyForm frontend images"
```

### 2. Setup Backend Service

Create Network Endpoint Group (NEG) for the backend Cloud Run service:

```bash
gcloud compute network-endpoint-groups create easyform-backend-neg \
  --region=us-central1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=easyform-backend
```

Create backend service:

```bash
gcloud compute backend-services create easyform-backend-service \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --protocol=HTTP
```

Attach NEG to backend service:

```bash
gcloud compute backend-services add-backend easyform-backend-service \
  --global \
  --network-endpoint-group=easyform-backend-neg \
  --network-endpoint-group-region=us-central1
```

### 3. Deploy Backend

Backend deployment is automated via GitHub Actions on push to `main` branch.

Manual deployment (if needed):

```bash
# Build and push
docker build -t us-central1-docker.pkg.dev/cloud-run-hackathon-475303/easyform-backend-repo/backend:manual ./backend
docker push us-central1-docker.pkg.dev/cloud-run-hackathon-475303/easyform-backend-repo/backend:manual

# Deploy to Cloud Run
gcloud run deploy easyform-backend \
  --image=us-central1-docker.pkg.dev/cloud-run-hackathon-475303/easyform-backend-repo/backend:manual \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --vpc-connector=svpc-uscentral1 \
  --vpc-egress=private-ranges-only \
  --set-env-vars=DB_HOST=10.73.16.3,DB_PORT=3306,DB_USER=backend,DB_NAME=easyform,CHROMA_HOST=localhost,CHROMA_PORT=8000,RAG_CHUNK_SIZE=1000,RAG_CHUNK_OVERLAP=200,RAG_TOP_K_RESULTS=10 \
  --set-secrets=DB_PASSWORD=DB_PASSWORD:latest,SECRET_KEY=SECRET_KEY:latest,GOOGLE_API_KEY=GOOGLE_API_KEY:latest \
  --cpu=1 --memory=512Mi --min-instances=0 --max-instances=3
```

### 4. Setup Frontend Service

Create Network Endpoint Group (NEG) for the frontend Cloud Run service:

```bash
gcloud compute network-endpoint-groups create easyform-frontend-neg \
  --region=us-central1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=easyform-frontend
```

Create backend service with CDN enabled:

```bash
gcloud compute backend-services create easyform-frontend-service \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --protocol=HTTP \
  --enable-cdn
```

Attach NEG to frontend backend service:

```bash
gcloud compute backend-services add-backend easyform-frontend-service \
  --global \
  --network-endpoint-group=easyform-frontend-neg \
  --network-endpoint-group-region=us-central1
```

### 5. Deploy Frontend

Frontend deployment is automated via GitHub Actions on push to `main` branch.

Manual deployment (if needed):

```bash
# Build frontend
cd frontend
npm ci
npm run build

# Build and push Docker image
docker build -t us-central1-docker.pkg.dev/cloud-run-hackathon-475303/easyform-frontend-repo/frontend:manual -f Dockerfile.prebuilt .
docker push us-central1-docker.pkg.dev/cloud-run-hackathon-475303/easyform-frontend-repo/frontend:manual

# Deploy to Cloud Run
gcloud run deploy easyform-frontend \
  --image=us-central1-docker.pkg.dev/cloud-run-hackathon-475303/easyform-frontend-repo/frontend:manual \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --cpu=1 --memory=512Mi --min-instances=0 --max-instances=3
```

### 6. SSL Certificate for easyform-ai.com

Create a managed SSL certificate for the EasyForm domain:

```bash
gcloud compute ssl-certificates create easyform-managed-cert \
  --domains=easyform-ai.com,www.easyform-ai.com
```

Check certificate status:

```bash
gcloud compute ssl-certificates describe easyform-managed-cert
```

Wait until status is `ACTIVE` (can take up to 24 hours after DNS is configured).

### 7. Update URL Map

The URL map configuration is stored in `gcloud/easyform-url-map.yaml`. This file includes routing for both Piatto and EasyForm.

Import the updated URL map:

```bash
gcloud compute url-maps import piatto-url-map \
  --source=gcloud/easyform-url-map.yaml \
  --global
```

### 8. Update HTTPS Proxy

After the SSL certificate is provisioned (status: ACTIVE), update the HTTPS proxy to include both certificates:

```bash
gcloud compute target-https-proxies update piatto-https-proxy \
  --ssl-certificates=piatto-managed-cert,easyform-managed-cert \
  --url-map=piatto-url-map
```

### 9. DNS Configuration

Point your DNS A records to the load balancer IP (same as Piatto):

```bash
# Get the load balancer IP
gcloud compute addresses describe piatto-web-ip --global --format='get(address)'
```

Add A records for:
- `easyform-ai.com` → Load balancer IP
- `www.easyform-ai.com` → Load balancer IP

## Environment Variables

### Backend Environment Variables

Set via Cloud Run:

```
DB_HOST=10.73.16.3
DB_PORT=3306
DB_USER=backend
DB_NAME=easyform
CHROMA_HOST=localhost
CHROMA_PORT=8000
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200
RAG_TOP_K_RESULTS=10
```

Secrets (from Secret Manager):
- `DB_PASSWORD`
- `SECRET_KEY`
- `GOOGLE_API_KEY`

### Frontend Environment Variables

None required - all configuration is built into the static assets during build time.

## GitHub Actions Workflows

### Backend Workflow

File: `.github/workflows/prod-backend-docker.yml`

Triggers on:
- Push to `main` branch
- Changes in `backend/**`

Steps:
1. Build Docker image
2. Push to Artifact Registry
3. Deploy to Cloud Run with environment variables and secrets

### Frontend Workflow

File: `.github/workflows/prod-frontend-docker.yml`

Triggers on:
- Push to `main` branch
- Changes in `frontend/**`
- Manual workflow dispatch

Steps:
1. Build frontend assets (npm run build)
2. Build Docker image with Nginx
3. Push to Artifact Registry
4. Deploy to Cloud Run

## Verification

Test the setup:

```bash
# Test HTTP redirect to HTTPS
curl -I http://easyform-ai.com

# Test frontend
curl -I https://easyform-ai.com/

# Test backend API
curl -I https://easyform-ai.com/api/health

# Test asset loading
curl -I https://easyform-ai.com/assets/index-hash123.js
```

## CDN Cache Invalidation

If needed, invalidate the CDN cache for the frontend service:

```bash
gcloud compute backend-services invalidate-cdn-cache easyform-frontend-service \
  --global \
  --path "/*"
```

## Troubleshooting

### Certificate not activating
- Ensure DNS records are pointing to the correct IP
- Wait up to 24 hours for certificate provisioning

### Backend cannot connect to database
- Verify VPC connector is properly configured
- Check that the backend service has `--vpc-egress=private-ranges-only`
- Verify database credentials in Secret Manager

### Frontend not updating
- Invalidate CDN cache
- Check that GitHub Actions workflow completed successfully
- Verify Docker image was pushed to Artifact Registry

## Resource Costs

- **Cloud Run:** Pay per request (scales to zero when not in use)
- **Load Balancer:** ~$18/month base + per-GB transferred
- **Artifact Registry:** ~$0.10/GB stored
- **Cloud CDN:** ~$0.08/GB egress (varies by region)
- **SSL Certificates:** Free (Google-managed)

## Maintenance

### Updating the URL Map

1. Edit `gcloud/easyform-url-map.yaml`
2. Import the changes:
   ```bash
   gcloud compute url-maps import piatto-url-map \
     --source=gcloud/easyform-url-map.yaml \
     --global
   ```

### Scaling Configuration

To update resource limits:

```bash
gcloud run services update easyform-backend \
  --region=us-central1 \
  --cpu=2 \
  --memory=1Gi \
  --min-instances=1 \
  --max-instances=10
```

### Viewing Logs

```bash
# Backend logs
gcloud run logs read easyform-backend --region=us-central1 --limit=50

# Frontend logs
gcloud run logs read easyform-frontend --region=us-central1 --limit=50
```
