# idp-smart: Intelligent Document Processing

This repository contains the setup for the **idp-smart** system as described in the architecture diagram. It is designed to be the bridge between complex legal documents and structured data, taking advantage of Granite-Docling VLM and scalable microservices.

## Project Structure

```text
idp-smart/
├── docker-compose.yml       # Orchestrator for Valkey, MinIO, API, and Worker
├── Dockerfile               # Production-ready image for API & Celery Worker
├── requirements.txt         # Package dependencies (FastAPI, Celery, SQLAlchemy, Minio, etc.)
└── app/
    ├── main.py              # FastAPI application entrypoint (REST API)
    ├── core/
    │   ├── config.py        # Settings management for DB, MinIO, and Valkey
    │   └── minio_client.py  # Utility functions to interact with the MinIO Object Storage
    ├── db/
    │   ├── database.py      # Async SQLAlchemy connection setup
    │   └── models.py        # SQLAlchemy model (DocumentExtraction) to store form info
    ├── engine/              # IA Core processing logic
    │   ├── agent.py         # LangChain Agent module for mapping extracted text to JSON schema
    │   ├── mapper.py        # Logic to extract Form Schemas and map the final UUID payload
    │   └── vision.py        # Granite-Docling Document Converter implementation
    └── worker/
        └── celery_app.py    # Celery logic for async long-running IDP tasks
```

## Added Infrastructure Components
* **PostgreSQL (`idp_qa` local host)**: Track document form payloads, Act Type, Form Id, and extracted JSONs using SQLAlchemy models.
* **MinIO (S3 Compatible)**: Deployed automatically via docker-compose to isolate raw and processing PDF files. When the REST API receives a document, it persists the PDF/Images in a MinIO `idp-documents` bucket rather than using standard file systems, making horizontal scaling possible.
* **Valkey Broker**: Ensures Celery tasks are correctly enqueued for complex NLP text extraction.

## Setup & Running

1. **Start the environment** using Docker Compose:
   ```bash
   cd /home/casmartdb/.gemini/antigravity/scratch/idp-smart
   docker compose up -d --build
   ```

2. **Verify services**:

   - **Get Forms**: Fetch valid dynamic mapped forms from `cfdeffrmpre`:
     ```bash
     curl http://localhost:8000/api/v1/forms
     ```
   
   - **Process Document**: Dispatch an extraction task. With the latest changes, you must send `act_type` and `form_code` string fields inside the Form Data boundary:
     ```bash
     curl -X POST http://localhost:8000/api/v1/process \
          -F "act_type=Escritura" \
          -F "form_code=FORMA_1234" \
          -F "json_form=@form.json" \
          -F "document=@document.pdf"
     ```
   
   - **Check extraction status**: Check the DB (PostgreSQL) directly for the status of the previously launched task ID:
     ```bash
     curl http://localhost:8000/api/v1/status/YOUR_TASK_ID
     ```

## Environment Configs (`host.docker.internal`)

The `docker-compose.yml` configures the host-bridge networking explicitly:
* `DB_HOST=host.docker.internal` handles connectivity between the Dockerized Python Apps and your physical native `localhost:5432` PostgreSQL server (avoiding the need to provision a separate DB inside Docker while keeping the API containerized).

MinIO runs mapped directly to ports `9000` (API) and `9001` (Console panel). You can access the minio visual interface on `http://localhost:9001` with `admin / minio_password123`.
