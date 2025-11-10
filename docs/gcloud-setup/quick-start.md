# EasyForm GCloud Deployment - Quick Start Guide

Schnellanleitung für das Deployment von EasyForm auf Google Cloud Platform.

## Voraussetzungen

- GCloud CLI installiert und authentifiziert
- GitHub Repository mit konfiguriertem Secret `GCP_SA_KEY`
- Domain `easyform-ai.com` bereit für DNS-Konfiguration

## Schritt-für-Schritt Anleitung

### 1. GCloud Projekt aktivieren

```bash
gcloud config set project cloud-run-hackathon-475303
```

### 2. Artifact Registry Repositories erstellen

Führe die Setup-Skripte aus:

```bash
cd gcloud

# Backend Service Setup
bash setup-backend-service.sh

# Frontend Service Setup
bash setup-frontend-service.sh
```

### 3. Initiales Deployment

**Option A: Via GitHub Actions (empfohlen)**

Pushe deine Änderungen auf den `main` Branch:

```bash
git add .
git commit -m "Initial EasyForm deployment setup"
git push origin main
```

Die GitHub Actions Workflows deployen automatisch:
- Backend bei Änderungen in `backend/**`
- Frontend bei Änderungen in `frontend/**`

**Option B: Manuell**

```bash
# Backend deployen
cd backend
gcloud builds submit --tag us-central1-docker.pkg.dev/cloud-run-hackathon-475303/easyform-backend-repo/backend:v1

gcloud run deploy easyform-backend \
  --image=us-central1-docker.pkg.dev/cloud-run-hackathon-475303/easyform-backend-repo/backend:v1 \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --vpc-connector=svpc-uscentral1 \
  --vpc-egress=private-ranges-only \
  --set-env-vars=DB_HOST=10.73.16.3,DB_PORT=3306,DB_USER=backend,DB_NAME=easyform,CHROMA_HOST=localhost,CHROMA_PORT=8000,RAG_CHUNK_SIZE=1000,RAG_CHUNK_OVERLAP=200,RAG_TOP_K_RESULTS=10 \
  --set-secrets=DB_PASSWORD=DB_PASSWORD:latest,SECRET_KEY=SECRET_KEY:latest,GOOGLE_API_KEY=GOOGLE_API_KEY:latest \
  --cpu=1 --memory=512Mi --min-instances=0 --max-instances=3

# Frontend deployen
cd ../frontend
npm ci && npm run build
gcloud builds submit --tag us-central1-docker.pkg.dev/cloud-run-hackathon-475303/easyform-frontend-repo/frontend:v1 -f Dockerfile.prebuilt

gcloud run deploy easyform-frontend \
  --image=us-central1-docker.pkg.dev/cloud-run-hackathon-475303/easyform-frontend-repo/frontend:v1 \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --cpu=1 --memory=512Mi --min-instances=0 --max-instances=3
```

### 4. Load Balancer konfigurieren

```bash
cd gcloud
bash setup-load-balancer.sh
```

Dieser Schritt:
- Erstellt SSL-Zertifikat für `easyform-ai.com`
- Aktualisiert die URL-Map für Routing
- Zeigt Befehle zum Aktualisieren des HTTPS-Proxys

### 5. DNS konfigurieren

Hole die Load Balancer IP:

```bash
gcloud compute addresses describe piatto-web-ip --global --format='get(address)'
```

Erstelle A-Records bei deinem DNS-Provider:

```
easyform-ai.com        → [Load Balancer IP]
www.easyform-ai.com    → [Load Balancer IP]
```

### 6. SSL-Zertifikat verifizieren

Warte, bis das Zertifikat aktiv ist (kann 5-20 Minuten dauern):

```bash
watch -n 30 gcloud compute ssl-certificates describe easyform-managed-cert
```

Status sollte `ACTIVE` sein.

### 7. HTTPS-Proxy aktualisieren

Sobald das Zertifikat aktiv ist:

```bash
gcloud compute target-https-proxies update piatto-https-proxy \
  --ssl-certificates=piatto-managed-cert,easyform-managed-cert \
  --url-map=piatto-url-map
```

### 8. Testen

```bash
# Frontend Test
curl -I https://easyform-ai.com/

# Backend API Test
curl -I https://easyform-ai.com/api/health

# HTTP → HTTPS Redirect
curl -I http://easyform-ai.com/
```

## Häufige Probleme

### "Service easyform-backend not found"

Die Services müssen erst deployed werden, bevor die NEGs erstellt werden können.

**Lösung:**
1. Deploye zuerst die Services (Schritt 3)
2. Dann erstelle die Backend Services und NEGs (Schritt 2)

### Zertifikat wird nicht aktiv

**Mögliche Ursachen:**
- DNS ist nicht korrekt konfiguriert
- Propagation dauert noch

**Lösung:**
- DNS-Konfiguration prüfen
- Bis zu 24h warten

### Backend kann nicht auf DB zugreifen

**Lösung:**
- VPC Connector prüfen: `gcloud compute networks vpc-access connectors describe svpc-uscentral1 --region=us-central1`
- DB-Credentials in Secret Manager prüfen

## Continuous Deployment

Nach dem initialen Setup werden Updates automatisch deployed:

1. **Backend Updates:** Push zu `main` mit Änderungen in `backend/**`
2. **Frontend Updates:** Push zu `main` mit Änderungen in `frontend/**`

Workflows sind definiert in:
- [.github/workflows/prod-backend-docker.yml](../../.github/workflows/prod-backend-docker.yml)
- [.github/workflows/prod-frontend-docker.yml](../../.github/workflows/prod-frontend-docker.yml)

## Nächste Schritte

- [ ] Monitoring & Logging einrichten
- [ ] Backup-Strategie für die Datenbank
- [ ] Cloud Armor für DDoS-Schutz
- [ ] Custom Domain für Cloud Run URLs
- [ ] Alerting für Fehler und Performance

## Hilfreiche Befehle

```bash
# Logs anzeigen
gcloud run logs read easyform-backend --region=us-central1 --limit=100
gcloud run logs read easyform-frontend --region=us-central1 --limit=100

# Service-Status prüfen
gcloud run services describe easyform-backend --region=us-central1
gcloud run services describe easyform-frontend --region=us-central1

# URL-Map exportieren
gcloud compute url-maps export piatto-url-map --global > current-url-map.yaml

# CDN Cache löschen
gcloud compute backend-services invalidate-cdn-cache easyform-frontend-service --global --path "/*"
```

## Support

Vollständige Dokumentation: [setup-protocol.md](setup-protocol.md)
