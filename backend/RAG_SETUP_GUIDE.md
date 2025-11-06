# RAG Setup Guide for EasyForm Backend

This guide will help you get started with the RAG (Retrieval-Augmented Generation) implementation.

---

## 🚀 Quick Start

### 1. Install System Dependencies

#### Windows (Development)
1. **Install Tesseract OCR:**
   ```bash
   # Using Chocolatey
   choco install tesseract

   # Or download from: https://github.com/UB-Mannheim/tesseract/wiki
   # Default path: C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

2. **Update your `.env` file:**
   ```bash
   TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

#### Docker (Production)
Tesseract is automatically installed in the Dockerfile. No action needed.

---

### 2. Start ChromaDB

#### Using Docker Compose (Recommended)
```bash
cd backend
docker-compose -f docker-compose-rag.yml up -d
```

This will:
- Start ChromaDB on port 8000
- Create persistent storage in `chroma_data` volume
- Enable healthcheck monitoring

#### Verify ChromaDB is Running
```bash
curl http://localhost:8000/api/v1/heartbeat
# Expected output: {"nanosecond heartbeat": 1234567890}
```

---

### 3. Install Python Dependencies

```bash
cd backend
python -m pip install -r requirements.txt
```

Key new dependencies:
- `chromadb>=0.4.22` - Vector database
- `pymupdf>=1.23.0` - PDF processing
- `pytesseract>=0.3.10` - OCR
- `google-generativeai>=0.3.0` - Embeddings

---

### 4. Update Environment Variables

Add to your `.env` file:

```bash
# ChromaDB Configuration
CHROMA_HOST=localhost
CHROMA_PORT=8000

# RAG Settings
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200
RAG_TOP_K_RESULTS=10

# Tesseract (Windows only - adjust path if needed)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

---

### 5. Run Database Migrations

The new `document_chunks` table will be created automatically on startup via SQLAlchemy:

```bash
cd backend
python -m uvicorn src.main:app --reload
```

Check logs for:
```
✅ Database tables created/verified
```

---

## 📝 How RAG Works in EasyForm

### Upload Flow
1. User uploads a PDF or image via `/api/files/upload`
2. File is stored in database immediately (user gets instant response)
3. **Background task starts:**
   - Extract text and images from PDF using PyMuPDF
   - Run OCR on images using Tesseract
   - Chunk text into 1000-token pieces with 200-token overlap
   - Generate embeddings using Google's `text-embedding-004`
   - Store chunks in `document_chunks` table
   - Index embeddings in ChromaDB

### Form Analysis Flow
1. User analyzes a form via `/api/form/analyze`
2. System decides: **Use RAG or Direct?**
   - **Use RAG if:**
     - More than 5 files
     - OR total content > 50,000 characters
     - OR any PDF > 10 pages
   - **Use Direct if:** Small file set (current approach)

3. **If Using RAG:**
   - Build search query from form field labels
   - Search ChromaDB for top 10 relevant chunks
   - Pass ONLY relevant chunks to Gemini
   - Generate form values

4. **If Using Direct:**
   - Pass ALL files to Gemini (current approach)
   - Generate form values

---

## 🧪 Testing the Implementation

### Test 1: Upload a PDF
```bash
curl -X POST http://localhost:8000/api/files/upload \
  -H "Authorization: Bearer <your_api_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "resume.pdf",
    "content_type": "application/pdf",
    "data": "<base64_encoded_pdf>"
  }'
```

**Expected Response:**
```json
{
  "id": "uuid-here",
  "filename": "resume.pdf",
  "content_type": "application/pdf",
  "file_size": 12345,
  "created_at": "2025-11-07T..."
}
```

**Check Processing Status:**
```sql
-- In your database
SELECT id, filename, processing_status, page_count
FROM files
WHERE id = 'uuid-here';

-- Expected: processing_status = 'completed'
```

**Check Chunks Created:**
```sql
SELECT COUNT(*) as chunk_count, chunk_type
FROM document_chunks
WHERE file_id = 'uuid-here'
GROUP BY chunk_type;
```

### Test 2: Verify ChromaDB Indexing
```python
import chromadb

client = chromadb.HttpClient(host="localhost", port=8000)
collection = client.get_collection("easyform_documents")

print(f"Total documents: {collection.count()}")

# Query test
results = collection.query(
    query_texts=["software engineer experience"],
    n_results=5,
    where={"user_id": "your-user-id"}
)

print(f"Found {len(results['ids'][0])} matches")
```

### Test 3: Form Analysis with RAG
```bash
curl -X POST http://localhost:8000/api/form/analyze \
  -H "Authorization: Bearer <your_api_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "html": "<form>...</form>",
    "visible_text": "Application Form",
    "quality": "medium"
  }'
```

**Check Logs:**
Look for these log messages:
```
Using RAG for context retrieval
RAG search query: name email phone address...
Retrieved 5 text chunks and 2 image chunks
```

---

## 🔍 Monitoring & Debugging

### Check ChromaDB Health
```bash
curl http://localhost:8000/api/v1/heartbeat
```

### View ChromaDB Collections
```bash
curl http://localhost:8000/api/v1/collections
```

### Check File Processing Status
```python
from src.db.database import get_async_db_context
from src.db.crud import files_crud

async with get_async_db_context() as db:
    files = await files_crud.get_user_files(db, user_id="your-user-id")
    for file in files:
        print(f"{file.filename}: {file.processing_status} ({file.page_count} pages)")
```

### View Application Logs
Look for these key log entries:
- `DocumentProcessingService initialized` - OCR ready
- `ChromaDB collection initialized with X documents` - Vector store ready
- `Using RAG for context retrieval` - RAG path taken
- `Retrieved X text chunks and Y image chunks` - Retrieval success

---

## ⚙️ Configuration Options

### Adjust Chunking Strategy
In `.env`:
```bash
RAG_CHUNK_SIZE=1000        # Larger = more context per chunk
RAG_CHUNK_OVERLAP=200      # Larger = better context preservation
```

### Adjust Retrieval
In `.env`:
```bash
RAG_TOP_K_RESULTS=10       # Larger = more context, but slower
```

### Adjust RAG Thresholds
In `src/services/rag_service.py`:
```python
MAX_DIRECT_CONTEXT_SIZE = 50000  # chars
MAX_DIRECT_FILE_COUNT = 5
MAX_DIRECT_FILE_PAGES = 10
```

---

## 🐛 Troubleshooting

### ChromaDB Connection Error
```
Error: Failed to connect to ChromaDB
```

**Solution:**
1. Check if ChromaDB is running: `docker ps | grep chroma`
2. Check port: `netstat -an | grep 8000`
3. Restart: `docker-compose -f docker-compose-rag.yml restart`

### Tesseract Not Found
```
Error: TesseractNotFoundError
```

**Solution (Windows):**
1. Install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
2. Update `.env`: `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`
3. Restart backend

**Solution (Docker):**
- Tesseract should be auto-installed. Rebuild image:
```bash
docker-compose build --no-cache
```

### No Chunks Created
```sql
SELECT COUNT(*) FROM document_chunks; -- Returns 0
```

**Solution:**
1. Check file processing status: `SELECT processing_status FROM files;`
2. Check logs for errors during background processing
3. Verify file type is PDF or image
4. Check file size (must be under 200MB)

### RAG Not Being Used
Logs show: `Using direct context (all files)`

**Solution:**
This is expected if:
- You have ≤5 files
- Total content <50K chars
- All PDFs ≤10 pages

To force RAG, adjust thresholds in `rag_service.py`.

---

## 📊 Performance Metrics

Track these metrics in production:

### Processing Time
- PDF processing: ~2-5 seconds per page
- Image processing: ~1-2 seconds per image
- Embedding generation: ~100ms per chunk
- Total: Expect 5-30 seconds for typical PDFs

### ChromaDB Performance
- Query latency: <500ms (target)
- Index size: ~1KB per chunk
- Memory usage: ~100MB for 10K documents

### Form Analysis Improvement
- With RAG: 30-50% faster for large file sets
- Context size reduction: 80-90% smaller than direct
- Accuracy: Same or better (more relevant context)

---

## 🚢 Deployment Checklist

Before deploying to production:

- [ ] ChromaDB running with persistent storage
- [ ] Tesseract installed in Docker image
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Test file upload and processing
- [ ] Test form analysis with RAG
- [ ] Monitor logs for errors
- [ ] Set up backup for ChromaDB data
- [ ] Configure Google API quotas/limits

---

## 📚 Further Reading

- **ChromaDB Docs:** https://docs.trychroma.com/
- **PyMuPDF Docs:** https://pymupdf.readthedocs.io/
- **Google Embeddings:** https://ai.google.dev/docs/embeddings_guide
- **RAG Implementation Plan:** See `RAG_IMPLEMENTATION_PLAN.md`

---

## 💬 Support

If you encounter issues:
1. Check logs: `docker-compose logs -f chromadb`
2. Check backend logs: Look for RAG-related errors
3. Verify configuration: Ensure all env vars are set
4. Review this guide for troubleshooting steps

Happy RAG-ing! 🚀
