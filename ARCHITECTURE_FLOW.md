# EasyForm - Three-Agent Architecture Flow

## Overview

EasyForm uses a three-agent pipeline with RAG-enhanced context retrieval to analyze web forms and generate browser actions. The system intelligently switches between direct file context and vector search based on data volume.

---

## Complete Processing Flow

```
Browser Extension → Backend API → Agent 1 (Parser) → Agent 2 (Solution Generator) → Agent 3 (Action Generator) → Browser Actions
                                          ↓
                                    RAG Service (conditional)
                                          ↓
                                  Vector Store (ChromaDB)
```

---

## Agent 1: HTML Form Parser Agent

**Purpose**: Extract structured form questions from raw HTML

**Location**: [`agent_service.py::parse_form_structure`](backend/src/services/agent_service.py#L110-L156)

**Model**: Gemini 2.5 Flash or Pro (based on quality profile)

### Input Context
- HTML code (sanitized)
- Visible DOM text
- Screenshots (optional, extended mode only) - **passed directly, never through RAG**
- Personal instructions

### Output
Structured list of questions, each containing:
- `question_id`: Unique identifier
- `question_type`: text, select, radio, checkbox, date, etc.
- `title`: Question label/title
- `description`: Additional context
- `context`: Surrounding page context
- `hints`: Validation cues, placeholders
- `inputs`: Array of input elements with:
  - `input_id`: Unique input identifier
  - `input_type`: HTML input type
  - `selector`: CSS selector for DOM element
  - `option_label`: Label for radio/checkbox options
  - `current_value`: Pre-filled value if any
  - `constraints`: Validation rules
  - `value_hint`: Placeholder or expected format

### Key Features
- Groups related inputs (e.g., first name + last name)
- Detects existing values
- Captures validation metadata
- Handles complex forms (grids, conditional fields)

---

## Agent 2: Solution Generator Agent (Critical Step)

**Purpose**: Generate natural-language answers for each form question using user context

**Location**: [`form_service.py::process_form_analysis_async`](backend/src/services/form_service.py#L736-L870) orchestrates retrieval, [`agent_service.py::generate_solutions_per_question`](backend/src/services/agent_service.py#L321-L520) executes LLM calls.

**Model**: Gemini 2.5 Flash or Pro (based on quality profile)

**Tools**: Uses Tools to solve questions

### 🔍 RAG Decision Logic

**Location**: [`form_service.py::process_form_analysis_async`](backend/src/services/form_service.py#L772-L830)

The system decides between two modes:

#### Direct Context Mode (Small datasets)
**Thresholds** ([`rag_service.py::should_use_rag`](backend/src/services/rag_service.py#L100-L142)):
- ≤ 5 files
- ≤ 50,000 characters total
- ≤ 10 PDF pages per file

**Behavior**: All user files (PDFs + images) passed directly to each agent call

#### RAG Mode (Large datasets)
**Triggered when**:
- > 5 files, OR
- > 50k characters, OR
- Any PDF > 10 pages

**Behavior**: Vector search retrieves relevant chunks (one retrieval per question during Step 2)

---

### 📊 RAG Retrieval Process (Step 2 Focus)

#### When RAG is Used:

**1. Question-Specific Query Construction** ([`form_service.py::build_search_query_for_question`](backend/src/services/form_service.py#L950-L989))

```python
question_query = build_search_query_for_question(question)
```

- Executed in `process_form_analysis_async` prior to invoking Agent 2.
- Blends the question title, description, hints, option labels, and metadata into a focused semantic query.

**2. Per-question RAG Retrieval Call** ([`form_service.py::process_form_analysis_async`](backend/src/services/form_service.py#L772-L824))

```python
context = await rag_service.retrieve_relevant_context(
    db=db,
    query=question_query,
    user_id=user_id,
    top_k=10
)
```

- Each question issues its own call to `retrieve_relevant_context` before Agent 2 is scheduled.
- Calls reuse the analysis DB session but run sequentially to avoid session contention.
- Returned chunks are stored in a map and passed to Agent 2; nothing is reused across questions.

**⚠️ CRITICAL**: RAG retrieval now happens **once per question**, aligning context granularity with each Step 2 prompt.

**3. RAG Service Retrieval** ([`rag_service.py::retrieve_relevant_context`](backend/src/services/rag_service.py#L144-L213))

**Process**:

1. Generate query embedding (768-dim vector from Google `text-embedding-004`)
2. Search ChromaDB collection with cosine similarity
3. Retrieve top 10 chunks (mixed: text + images)
4. Fetch full chunk data from PostgreSQL/MySQL
5. Separate by type:
    - **Text chunks**: content field contains text
    - **Image chunks**: raw_content field contains image bytes + content field contains OCR text
6. Return both lists

**Return format**:

```python
{
    "text_chunks": [
        {
            "content": "John Doe, born 1990-05-15...",
            "source": "resume.pdf (page 1)",
            "file_id": "...",
            "similarity": 0.87
        },
        # ... more text chunks
    ],
    "image_chunks": [
        {
            "image_bytes": b"...",           # Actual image data
            "description": "Driver license", # OCR text
            "source": "id_card.pdf (page 2)",
            "file_id": "...",
            "similarity": 0.82
        },
        # ... more image chunks
    ]
}
```

---

### 🤖 Per-Question Agent Execution

**Multiple Agents**: YES - One agent call per question, executed in parallel

**Concurrency**: Semaphore of 10 (max 10 parallel agent calls)

**Per-question retrieval**: Each task performs its own `retrieve_relevant_context` lookup before invoking the LLM.

**Location**: [`agent_service.py`](backend/src/services/agent_service.py#L385-L494)

```python
async def process_question(question_idx: int, question: dict):
    async with semaphore:  # Max 10 concurrent
        # ... build prompt with RAG context
        result = await solution_agent.run(...)
        return {"question_id": ..., "solution": ...}

tasks = [process_question(idx, q) for idx, q in enumerate(questions)]
results = await asyncio.gather(*tasks)  # Parallel execution
```

**Each question receives**:

1. Question metadata (from Agent 1)
2. **Question-specific RAG context** (text/image chunks fetched for that prompt)
3. Visible page text
4. Clipboard text (session instructions)
5. Personal instructions

---

### 🖼️ Image Handling in RAG

#### Image Embedding Strategy

**Location**: [`embedding_service.py::embed_image`](backend/src/services/embedding_service.py#L66-L93)

**Key Design**: Images are embedded using their **OCR text caption**, not pixel data

**Why?**
- Keeps text and images in the **same 768-dim embedding space**
- Enables unified semantic search across modalities
- Model: Google `text-embedding-004` (same as text)

**Process**:
1. Extract text from image via Tesseract OCR
2. Embed the OCR text (not image pixels)
3. Store both:
   - Embedding vector (768-dim) → ChromaDB
   - Original image bytes → Database `raw_content` field
   - OCR text → Database `content` field

**Fallback**: If OCR yields no text → embed `"[Image content]"` as placeholder

#### Image Retrieval and Usage

**Both text and image RAG are fetched together** for each question-specific search call.

**Text chunks usage**:
- Top 5 chunks included in prompt as text
- Format: `"From resume.pdf (page 1): John Doe, Software Engineer..."`

**Image chunks usage**:
- Image bytes (`raw_content`) passed to multimodal model
- OCR description included in prompt context
- Model can "see" the actual images

**Implementation** ([`agent_service.py`](backend/src/services/agent_service.py#L360-L470)):

```python
# RAG mode (question scoped)
if question_context:
    rag_images = question_context.get("image_chunks", [])
    for img_chunk in rag_images:
        images.append(img_chunk["image_bytes"])  # Actual image data

# Screenshots always passed directly (never through RAG)
if screenshots:
    images.extend(screenshots)

# All images sent to multimodal model for this question
content = create_multipart_query(
    query=solution_query,
    images=images
)
```

---

### 📸 Screenshot Handling

**CRITICAL**: Screenshots are **NEVER indexed in RAG**!

**Flow**:
1. Browser extension captures screenshot
2. Screenshot passed to Agent 1 (Parser) and Agent 2 (Solution Generator)
3. Screenshot sent directly to multimodal model (not stored in ChromaDB)
4. Valid only for current form analysis request

**Why not RAG?**
- Screenshots are request-specific (current page state)
- Stored files are persistent user documents
- Separate concerns: transient vs. permanent context

---

### Output

List of question-solution pairs:
```python
[
    {
        "question_id": "q1",
        "question": {...},  # Full question object from Agent 1
        "solution": "John Doe"
    },
    {
        "question_id": "q2",
        "question": {...},
        "solution": "john.doe@example.com"
    },
    # ... one per question
]
```

---

## Agent 3: Action Generator Agent

**Purpose**: Convert question-solution pairs into browser-executable actions

**Location**: [`agent_service.py::generate_actions_from_solutions`](backend/src/services/agent_service.py#L499-L625)

**Model**: Gemini 2.5 Flash or Pro (based on quality profile)

### Input
- Question-solution pairs from Agent 2
- No additional context needed (everything is in the solutions)

### Processing Strategy
**Batching**: Processes 10 questions per batch (configurable)

**Why batching?**
- Reduces API calls (10 questions → 1 API call)
- Maintains context across related questions
- Optimizes cost and latency

**Example batch**:
```json
[
    {
        "index": 1,
        "question_id": "q1",
        "question_type": "text",
        "title": "Full Name",
        "inputs": [{"input_id": "name", "selector": "#name", ...}],
        "solution": "John Doe"
    },
    // ... 9 more questions
]
```

### Output
Flat list of browser actions:
```python
{
    "actions": [
        {
            "action_type": "fillText",
            "selector": "#name",
            "value": "John Doe",
            "label": "Full Name"
        },
        {
            "action_type": "selectRadio",
            "selector": "input[name='gender'][value='male']",
            "value": null,
            "label": "Gender: Male"
        },
        # ... all actions from all questions
    ]
}
```

**Action types**:
- `fillText`: Fill text inputs, textareas
- `selectDropdown`: Select dropdown option by value
- `selectRadio`: Click radio button
- `selectCheckbox`: Toggle checkbox
- `click`: Click button/link

---

## Data Flow Summary

### Context Assembly at Each Stage

| Agent | HTML | Visible Text | Clipboard | Personal Instructions | Screenshots | User Files | RAG Context |
|-------|------|--------------|-----------|----------------------|-------------|------------|-------------|
| **Agent 1 (Parser)** | ✅ | ✅ | ❌ | ✅ | ✅ Direct | ❌ | ❌ |
| **Agent 2 (Solution)** | ❌ | ✅ | ✅ | ✅ | ✅ Direct | ✅ or RAG | ✅ or Direct |
| **Agent 3 (Action)** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### RAG Context Usage

**Per-question retrieval**:
- Query built from the current question’s title, description, hints, and key option labels
- Top 10 chunks retrieved (mixed text + images) for that question alone
- **Context kept isolated per question** so prompts stay focused

**Why retrieve per question?**
- Increases precision for multi-question forms with very different data requirements
- Reduces prompt clutter by excluding irrelevant chunks from sibling questions
- Plays nicely with per-question retries; failures only repeat the small lookup they need
- Works with the existing semaphore to avoid overwhelming the vector store despite higher call counts

---

## Document Processing Pipeline

### Upload Flow

**Location**: [`rag_service.py::process_and_index_file`](backend/src/services/rag_service.py#L29-L98)

```
User uploads file → Document Processor → Chunker → Embedder → ChromaDB + Database
```

### PDF Processing

**Location**: [`document_processing_service.py::process_pdf`](backend/src/services/document_processing_service.py#L36-L132)

**Per page**:
1. Extract text → Chunk with overlap (1000 tokens/chunk, 200 overlap)
2. Extract images → OCR with Tesseract → Resize to 1024×1024

**Output**: List of chunks (text + image)

### Image Processing

**Location**: [`document_processing_service.py::process_image`](backend/src/services/document_processing_service.py#L134-L182)

1. OCR entire image
2. Resize to 1024×1024
3. Create single chunk

### Embedding Generation

**Location**: [`embedding_service.py::add_chunks`](backend/src/services/embedding_service.py#L95-L161)

**For each chunk**:
1. Generate embedding (text or image via OCR)
2. Store in ChromaDB:
   - `embedding`: 768-dim vector
   - `document`: Text content (OCR text for images)
   - `metadata`: user_id, file_id, chunk_id, chunk_type, page, etc.
   - `id`: chunk_id
3. Store in database:
   - `content`: Text or OCR text
   - `raw_content`: Image bytes (if image chunk)
   - `metadata_json`: Page numbers, indices

---

## Quality Profiles

**Location**: [`agent_service.py::MODEL_CONFIG`](backend/src/services/agent_service.py#L29-L50)

| Profile | Agent 1 (Parser) | Agent 2 (Solution) | Agent 3 (Action) | Use Case |
|---------|------------------|--------------------|--------------------|----------|
| **fast** | Flash | Flash | Flash | Quick analysis, simple forms |
| **fast-pro** | Pro | Flash | Pro | Accurate parsing, fast solutions |
| **exact** | Flash | Pro | Flash | Complex reasoning, basic structure |
| **exact-pro** | Pro | Pro | Pro | Maximum quality, complex forms |

**Rationale**:
- **Agent 1 (Parser)**: Structural task, Flash often sufficient
- **Agent 2 (Solution)**: Reasoning-heavy, benefits from Pro
- **Agent 3 (Action)**: Structured output, matches Agent 1 for consistency

---

## Key Design Decisions

### 1. Three-Agent Separation
**Why not single agent?**
- Separation of concerns (structure vs. content vs. execution)
- Enables quality profile tuning per stage
- Parser and Action agents use structured output (Pydantic schemas)
- Solution agent needs reasoning (natural language)

### 2. RAG Threshold Design
**Why 5 files / 50k chars / 10 pages?**
- Balance between token limits and context quality
- Small datasets: Direct injection provides full context
- Large datasets: RAG avoids token overflow and focuses on relevance

### 3. Per-Question Parallel Processing
**Why separate calls?**
- Questions often have different context needs
- Parallel execution improves latency (10x speedup with 10 questions)
- Semaphore prevents overwhelming API rate limits
- Enables granular error handling

### 4. Per-Question RAG Retrieval
**Why fetch context for every question?**
- Guarantees that niche fields (e.g., license numbers vs. employment history) get the most relevant snippets
- Keeps multimodal attachments (PDF pages, extracted images) aligned with the active prompt
- Allows selective retries when a single question fails without reusing stale context for others
- Top-k naturally covers multiple intents
- Same context ensures consistency across form

### 5. Image Embedding via OCR
**Why not pixel embeddings?**
- Unified embedding space (768-dim for both text and images)
- Semantic search works across modalities
- Cheaper (text embedding vs. image embedding models)
- Sufficient for document images (forms, IDs, resumes)

### 6. Screenshot Exclusion from RAG
**Why not index screenshots?**
- Ephemeral: Page state changes constantly
- Request-specific: Only relevant to current form
- Persistent files: User documents for reuse
- Clear lifecycle: Transient vs. permanent

---

## Error Handling

### Agent Failures
- Each agent has retry logic (max_retries=3, retry_delay=1s)
- Per-question failures in Agent 2 don't block other questions
- Batch failures in Agent 3 return empty actions

### RAG Failures
- RAG search failure → returns empty context → agents still proceed
- Embedding failures → chunk skipped during indexing
- OCR failures → fallback to `"[Image content]"` placeholder

### Status Tracking

**Location**: [`form_service.py::process_form_analysis_async`](backend/src/services/form_service.py#L615-L930)

Database status progression:
1. `pending` → Request created
2. `processing_step_1` → Agent 1 (Parser) running
3. `processing_step_2` → Agent 2 (Solution) running
4. `processing_step_3` → Agent 3 (Action) running (implicit)
5. `completed` → Actions saved, ready for browser
6. `failed` → Error with message

Client polls status endpoint to monitor progress.

---

## Performance Characteristics

### Latency Breakdown (typical)

**Fast mode (Gemini Flash)**:
- Agent 1 (Parser): 2-5s
- Agent 2 (Solution): 3-8s per question (parallelized)
- Agent 3 (Action): 2-4s per batch
- **Total**: ~10-20s for 10-question form

**Exact-Pro mode (Gemini Pro)**:
- Agent 1 (Parser): 5-10s
- Agent 2 (Solution): 8-15s per question
- Agent 3 (Action): 5-8s per batch
- **Total**: ~25-40s for 10-question form

### Scaling

**Questions**: Linear (parallelized with semaphore)
- 5 questions: ~8s
- 50 questions: ~25s (10 concurrent)

**Files**:
- Direct mode: Linear with file count/size
- RAG mode: Scales with question count (one retrieval per question)

**RAG Retrieval**: O(log n) with ChromaDB HNSW index

---

## Future Optimizations

### Potential Improvements
1. **Streaming responses**: Show actions as they're generated
2. **Cache RAG results**: Reuse for similar forms
3. **Question grouping**: Batch related questions for Agent 2
4. **Hybrid retrieval**: Combine keyword + semantic search
5. **Image embedding models**: Direct pixel embeddings for better visual understanding
6. **Progressive refinement**: Start with fast mode, refine with pro on user request

### Current Limitations
1. **Higher RAG volume**: Per-question lookups increase embedding and Chroma loads
2. **Top-k=10 hardcoded**: Not adaptive to form complexity
3. **No reranking**: Initial retrieval results used directly
4. **OCR-only images**: Visual features not captured
5. **No conversation memory**: Each form analysis is stateless

---

## Conclusion

The three-agent architecture with selective RAG retrieval provides:
- ✅ Scalability: Handles small and large document collections
- ✅ Quality: Tunable via quality profiles
- ✅ Performance: Parallel processing with batching
- ✅ Flexibility: Direct vs. RAG automatically selected
- ✅ Multimodal: Text and images unified in semantic search

The key insight is **RAG is now per-question**, aligning context with each prompt while the semaphore keeps concurrency under control.
