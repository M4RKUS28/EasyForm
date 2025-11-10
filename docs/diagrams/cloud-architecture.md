# EasyForm Cloud Architecture

```mermaid
graph TD
    subgraph CI_CD[CI/CD Pipeline]
        Dev[Developer commits] --> GH[GitHub Repository]
        GH --> CI[GitHub Actions Workflows\n(prod-backend / prod-frontend)]
        CI --> AR[Artifact Registry\nus-central1]
    end

    subgraph GCP[Google Cloud Platform (us-central1)]
        LB[Global HTTPS Load Balancer\npiatto-url-map]
        FE[Cloud Run Service\n`easyform-frontend`]
        BE[Cloud Run Service\n`easyform-backend`]
        Secrets[Secret Manager]
        VPC[Serverless VPC Connector\n`svpc-uscentral1`]
        SQL[(Cloud SQL\nMySQL)]
        Vertex[Vertex AI\nmultimodalembedding@001]
        Gemini[Google AI Gemini APIs]
    end

    Chroma[Managed ChromaDB\nchromadb.m4rkus28.de]
    Browser[End User Browser]

    CI -->|Deploy container| FE
    CI -->|Deploy container| BE
    Browser -->|HTTPS| LB
    LB -->|Static SPA| FE
    LB -->|/api/*| BE
    BE --> Secrets
    BE --> Vertex
    BE --> Gemini
    BE --> Chroma
    BE --> VPC --> SQL
    FE -->|Delivers UI| Browser
```
