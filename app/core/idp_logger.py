"""
idp-smart — Módulo de Logging de Ejecuciones
=============================================
Registra cada etapa del proceso de extracción en la tabla idp_smart.process_logs.
Provee un helper síncrono (para Celery) y uno asíncrono (para FastAPI).
"""
import time
import logging
from contextlib import contextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Logger estándar de Python (también escribe en stdout/stderr de Docker)
logger = logging.getLogger("idp_smart")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ---------------------------------------------------------------------------
# Helpers síncronos — usados por Celery
# ---------------------------------------------------------------------------

def log_event(
    engine: Engine,
    task_id: str,
    stage: str,
    message: str,
    level: str = "INFO",
    detail: dict | None = None,
    duration_ms: float | None = None,
) -> None:
    """
    Inserta un registro en process_logs usando el engine síncrono de SQLAlchemy
    (modo Celery). También emite el mensaje al logger estándar de Python.
    """
    log_fn = {
        "DEBUG":   logger.debug,
        "INFO":    logger.info,
        "WARNING": logger.warning,
        "ERROR":   logger.error,
    }.get(level, logger.info)

    log_fn("[%s] [%s] %s", task_id, stage, message)

    import json
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO idp_smart.process_logs
                        (task_id, stage, level, message, detail, duration_ms)
                    VALUES
                        (:task_id, :stage, :level, :message, :detail, :duration_ms)
                """),
                {
                    "task_id":     task_id,
                    "stage":       stage,
                    "level":       level,
                    "message":     message,
                    "detail":      json.dumps(detail) if detail else None,
                    "duration_ms": duration_ms,
                },
            )
    except Exception as exc:
        # El fallo de log no debe interrumpir el proceso principal
        logger.error("[%s] No se pudo escribir log en BD: %s", task_id, exc)


@contextmanager
def timed_stage(engine: Engine, task_id: str, stage: str, message: str, detail: dict | None = None):
    """
    Context manager que mide el tiempo de una etapa y la registra automáticamente.

    Uso:
        with timed_stage(engine, task_id, "VISION", "Extrayendo Markdown con Docling"):
            markdown = extract_markdown(...)
    """
    t0 = time.monotonic()
    log_event(engine, task_id, stage, f"INICIO — {message}", detail=detail)
    try:
        yield
        duration = (time.monotonic() - t0) * 1000
        log_event(engine, task_id, stage, f"FIN — {message}", duration_ms=round(duration, 2))
    except Exception as exc:
        duration = (time.monotonic() - t0) * 1000
        log_event(
            engine, task_id, stage,
            f"ERROR — {message}: {exc}",
            level="ERROR",
            detail={"error": str(exc), "type": type(exc).__name__},
            duration_ms=round(duration, 2),
        )
        raise


# ---------------------------------------------------------------------------
# JSON Simplificado — extrae solo {label: value} del JSON del sistema Java
# ---------------------------------------------------------------------------

def build_simplified_json(full_json: dict) -> dict:
    """
    Recorre el JSON completo del sistema Java y extrae un diccionario
    plano con el formato { "label": "value" } para cada control visible.

    Ejemplo de salida:
        {
          "Folio real electrónico": "12345678901234567890",
          "No. Notario": "42",
          "Nombre": "Juan Pérez García"
        }
    """
    simplified: dict[str, Any] = {}

    def _recurse(node, prefix=""):
        if isinstance(node, dict):
            # 1. Nodo de control con label y value
            if "label" in node and "value" in node:
                label = node.get("label", "").strip()
                value = node.get("value")
                if label and value is not None and value != "":
                    # Usar prefijo si estamos dentro de una instancia de matriz
                    display_label = f"{label} {prefix}".strip()
                    simplified[display_label] = value
            
            # 2. Soporte para MATRICES (instancias clonadas)
            if "instances" in node and isinstance(node["instances"], list):
                for i, instance in enumerate(node["instances"]):
                    # Añadimos un sub-prefijo numerado para distinguir propietarios, colindancias, etc.
                    _recurse(instance, prefix=f"({i+1})")
            
            # 3. Seguir recorriendo todos los valores anidados estándar
            for k, val in node.items():
                if k != "instances": # evitamos doble recorrido
                    _recurse(val, prefix=prefix)
                    
        elif isinstance(node, list):
            for item in node:
                _recurse(item, prefix=prefix)

    _recurse(full_json)
    return simplified
