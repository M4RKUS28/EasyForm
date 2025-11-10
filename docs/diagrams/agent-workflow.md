flowchart TB
 subgraph Frontend["Frontend"]
        UI["Browser Extension / Web App"]
  end
 subgraph Backend["FastAPI Backend"]
        Parser["Step 1 - HTML Form Parser Agent"]
        SolutionA["Step 2 - Solution Generator Agent"]
        SolutionB["Step 2 - Solution Generator Agent"]
        SolutionC["Step 2 - Solution Generator Agent"]
        Action["Step 3 - Action Generator Agent"]
        Fanout{{"Async fan-out - semaphore 10"}}
  end
 subgraph RAG["Retrieval Layer"]
        Proc["Document Processing - OCR + chunking"]
        TextEmb["Text Embeddings - Gemini gemini-embedding-001"]
        ImgEmb["Image Embeddings - Vertex AI multimodal@001"]
        TextStore[("Chroma Text Collection")]
        ImgStore[("Chroma Image Collection")]
  end
    UI -- Form HTML + context --> Parser
    Parser -- Structured questions --> Fanout
    UI -- Uploads --> Proc
    Proc --> TextEmb & ImgEmb
    TextEmb --> TextStore
    ImgEmb --> ImgStore
    Fanout -- Question query --> TextStore & ImgStore
    TextStore -- "Top-K chunks" --> SolutionA
    ImgStore -- "Top-K images" --> SolutionA
    Fanout --> SolutionA & SolutionB & SolutionC
    TextStore -.-> SolutionB & SolutionC
    ImgStore -.-> SolutionB & SolutionC
    SolutionA -- "Per-question solutions" --> Action
    SolutionB --> Action
    SolutionC --> Action
    Action -- Browser actions JSON --> UI

     Parser:::agent
     SolutionA:::agent
     SolutionB:::agent
     SolutionC:::agent
     Action:::agent
     TextStore:::store
     ImgStore:::store
    classDef agent fill:#004aad,stroke:#002a66,stroke-width:2,color:#fff
    classDef store fill:#0b8a42,stroke:#045626,stroke-width:2,color:#fff


