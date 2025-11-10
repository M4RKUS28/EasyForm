
flowchart TD


    subgraph GCP[Google Cloud Platform · us-central1]
        subgraph LB[Global HTTPS Load Balancer]
            URLMAP{URL Map}
        end

        subgraph CDN[Cloud CDN Edge]
            CDN_FE[(Cache: SPA routes)]
        end

        subgraph CR_FE[Cloud Run · Frontend]
            NEG_FE[Serverless NEG]
            SRV_FE[easyform-frontendservice]
            NGINX[Nginx container]
            try_files[try_files /try_files $uri $uri/ /index.html]
        end

        subgraph CR_BE[Cloud Run · Backend]
            NEG_BE[Serverless NEG]
            SRV_BE[easyform-backend service]
            UVICORN[Uvicorn workers]
            FASTAPI[FastAPI application]
        end

        subgraph DATA[Data ]
            SQL[(Cloud SQL · MySQL)]
            ChromaDB[ChromaDB]
        end

        Vertex[Vertex AI]
        Gemini[Google AI Gemini APIs]
    end

    Browser[Web Browser]
    Extension[Browser Add-on]


    Browser -->|HTTPS| URLMAP
    Extension -->|HTTPS| URLMAP

    URLMAP -->|/api/*| NEG_BE --> SRV_BE --> UVICORN --> FASTAPI
    URLMAP -->|SPA routes| CDN_FE --> NEG_FE --> SRV_FE --> NGINX --> try_files

    FASTAPI --> SQL
    FASTAPI --> Vertex
    FASTAPI --> Gemini
    FASTAPI --> ChromaDB

    classDef note fill:#fff7e6,stroke:#f0b15c,color:#5f4516;
    classDef entry fill:#e1f5fe,stroke:#0288d1,color:#01579b;
    classDef lb fill:#e8eaf6,stroke:#5c6bc0,color:#1a237e;
    classDef cdn fill:#f3e5f5,stroke:#8e24aa,color:#4a148c;
    classDef run fill:#e8f5e9,stroke:#43a047,color:#1b5e20;
    classDef neg fill:#ede7f6,stroke:#9575cd,color:#311b92;
    classDef data fill:#f5f5f5,stroke:#9e9e9e,color:#424242;
    classDef ext fill:#fff3e0,stroke:#fb8c00,color:#e65100;

    class Browser,Extension entry;
    class URLMAP lb;
    class CDN_FE cdn;
    class NEG_FE,NEG_BE neg;
    class SRV_FE,SRV_BE,NGINX,UVICORN,FASTAPI run;
    class SQL,Secrets data;
    class Extension ext;

