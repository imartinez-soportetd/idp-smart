from celery import Celery
from core.config import settings
from core.idp_logger import log_event, timed_stage, build_simplified_json
from core.minio_client import get_minio_client, upload_file_to_minio
from sqlalchemy import create_engine, text
import json
import traceback

# Import Engine Components
from engine.vision import extract_markdown_from_minio
from engine.agent import extract_form_data
from engine.mapper import get_json_schema, map_results_to_json

# Create celery application
celery_app = Celery(
    "idp_worker",
    broker=settings.valkey_url,
    backend=settings.valkey_url
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Mexico_City',
    enable_utc=True,
    worker_concurrency=4
)

# Sync engine for Celery
sync_database_url = settings.database_url.replace("postgresql+asyncpg", "postgresql")
db_engine = create_engine(sync_database_url)

# Etapas definidas del proceso (usadas para cálculo de progreso en frontend)
STAGES = ["INICIO", "VISION", "SCHEMA_LOAD", "AGENT", "MAPPER", "SIMPLIFY", "DB_SAVE", "ERROR"]


def _set_stage(task_id: str, stage: str, status: str = None):
    """Actualiza stage_current y status en la BD para que el frontend vea el avance."""
    try:
        with db_engine.begin() as conn:
            if status:
                conn.execute(
                    text("""
                        UPDATE idp_smart.document_extractions
                        SET stage_current = :stage, status = :status, updated_at = NOW()
                        WHERE task_id = :task_id
                    """),
                    {"stage": stage, "status": status, "task_id": task_id},
                )
            else:
                conn.execute(
                    text("""
                        UPDATE idp_smart.document_extractions
                        SET stage_current = :stage, updated_at = NOW()
                        WHERE task_id = :task_id
                    """),
                    {"stage": stage, "task_id": task_id},
                )
    except Exception as exc:
        log_event(db_engine, task_id, "SYSTEM", f"No se pudo actualizar stage_current a {stage}: {exc}", level="WARNING")


@celery_app.task(name="process_doc")
def process_doc(task_id: str, json_minio_object: str, pdf_minio_object: str):
    """
    Pipeline de extracción semántica de documentos:
    INICIO → VISION → SCHEMA_LOAD → AGENT → MAPPER → SIMPLIFY → DB_SAVE
    """
    minio_client = get_minio_client()

    try:
        # ── INICIO ───────────────────────────────────────────────────────────────
        _set_stage(task_id, "INICIO")
        log_event(db_engine, task_id, "INICIO",
                  f"Tarea iniciada — doc: {pdf_minio_object} | form: {json_minio_object}",
                  detail={"pdf": pdf_minio_object, "form": json_minio_object})

        # ── VISION ───────────────────────────────────────────────────────────────
        _set_stage(task_id, "VISION")
        doc_markdown = None
        with timed_stage(db_engine, task_id, "VISION", "Extracción Markdown con Granite-Docling"):
            doc_markdown = extract_markdown_from_minio(pdf_minio_object)  # Fix argument count
            if not doc_markdown:
                doc_markdown = "# Documento Fallback\nNo se pudo extraer contenido jerárquico."
                log_event(db_engine, task_id, "VISION",
                          "Docling no extrajo contenido, usando fallback de texto vacío.", level="WARNING")
            else:
                log_event(db_engine, task_id, "VISION",
                          f"Markdown generado: {len(doc_markdown)} caracteres extraídos.",
                          detail={"char_count": len(doc_markdown)})

        # Guardar el Markdown en MinIO para auditoría / re-procesamiento
        markdown_path = None
        try:
            md_bytes = doc_markdown.encode("utf-8")
            md_object_name = f"{task_id}/extracted_markdown.md"
            markdown_path = upload_file_to_minio(minio_client, md_object_name, md_bytes, "text/markdown")
            log_event(db_engine, task_id, "VISION",
                      f"Markdown persistido en MinIO: {markdown_path}",
                      detail={"minio_path": markdown_path})
            # Guardar la ruta del markdown en la BD
            with db_engine.begin() as conn:
                conn.execute(
                    text("UPDATE idp_smart.document_extractions SET markdown_minio_path = :path WHERE task_id = :tid"),
                    {"path": markdown_path, "tid": task_id},
                )
        except Exception as exc:
            log_event(db_engine, task_id, "VISION",
                      f"No se pudo guardar el markdown en MinIO: {exc}", level="WARNING")

        # ── SCHEMA_LOAD ──────────────────────────────────────────────────────────
        _set_stage(task_id, "SCHEMA_LOAD")
        schema = None
        with timed_stage(db_engine, task_id, "SCHEMA_LOAD", "Carga de esquema JSON desde MinIO"):
            schema = get_json_schema("idp-documents", json_minio_object)
            field_count = len(schema) if isinstance(schema, dict) else 0
            log_event(db_engine, task_id, "SCHEMA_LOAD",
                      f"Esquema JSON cargado con {field_count} campo(s) a extraer.",
                      detail={"field_count": field_count})

        # ── AGENT ─────────────────────────────────────────────────────────────────
        _set_stage(task_id, "AGENT")
        extracted_key_val = None
        with timed_stage(db_engine, task_id, "AGENT", "Extracción semántica con LangChain Agent"):
            extracted_key_val = extract_form_data(doc_markdown, schema)
            filled_count = sum(1 for v in extracted_key_val.values() if v) if extracted_key_val else 0
            total_count  = len(extracted_key_val) if extracted_key_val else 0
            log_event(db_engine, task_id, "AGENT",
                      f"Agente completó {filled_count}/{total_count} campos.",
                      detail={
                          "filled": filled_count, "total": total_count,
                          "fill_rate": f"{round(filled_count / total_count * 100, 1)}%" if total_count else "N/A"
                      })

        # ── MAPPER ────────────────────────────────────────────────────────────────
        _set_stage(task_id, "MAPPER")
        final_json = None
        with timed_stage(db_engine, task_id, "MAPPER", "Mapeo de UUIDs y reconstrucción del JSON"):
            final_json = map_results_to_json(schema, extracted_key_val)

        # ── SIMPLIFY ──────────────────────────────────────────────────────────────
        _set_stage(task_id, "SIMPLIFY")
        simplified = {}
        with timed_stage(db_engine, task_id, "SIMPLIFY", "Generación de JSON simplificado {label: value}"):
            simplified = build_simplified_json(final_json)
            log_event(db_engine, task_id, "SIMPLIFY",
                      f"JSON simplificado generado con {len(simplified)} campo(s).",
                      detail={"fields": list(simplified.keys())[:20]})

        # ── DB_SAVE ───────────────────────────────────────────────────────────────
        _set_stage(task_id, "DB_SAVE")
        with timed_stage(db_engine, task_id, "DB_SAVE", "Persistiendo resultado en PostgreSQL"):
            with db_engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE idp_smart.document_extractions
                        SET
                            status              = 'COMPLETED',
                            stage_current       = 'COMPLETADO',
                            extracted_data      = :full_json,
                            simplified_json     = :simplified_json,
                            updated_at          = NOW()
                        WHERE task_id = :task_id
                    """),
                    {
                        "full_json":       json.dumps(final_json),
                        "simplified_json": json.dumps(simplified),
                        "task_id":         task_id,
                    },
                )

        log_event(db_engine, task_id, "COMPLETADO",
                  "Tarea finalizada exitosamente.",
                  detail={"campos_llenados": len([v for v in simplified.values() if v])})

        return {"task_id": task_id, "status": "COMPLETED", "fields_filled": len(simplified)}

    except Exception as e:
        error_msg = f"Error general en task_id {task_id}: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        
        # Registrar el error como un log de evento general
        log_event(db_engine, task_id, "ERROR", error_msg, level="ERROR", detail={"traceback": traceback.format_exc()})
        
        # Setear explícitamente el STATUS como ERROR y la etapa actual.
        _set_stage(task_id, "ERROR", status="ERROR")
        
        return {"task_id": task_id, "status": "ERROR", "error": str(e)}
