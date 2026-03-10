import os
import tempfile
from core.minio_client import get_minio_client
from docling.document_converter import DocumentConverter

def extract_markdown_from_minio(object_name: str) -> str:
    """
    Descarga el documento de MinIO temporalmente y utiliza Docling (Granite-Docling)
    para convertir el documento jerárquico y sus tablas en Markdown puro.
    """
    client = get_minio_client()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        client.fget_object("idp-documents", object_name, tmp_file.name)
        tmp_path = tmp_file.name
        
    try:
        # Usa Docling para visión jerárquica
        converter = DocumentConverter()
        result = converter.convert(tmp_path)
        markdown_text = result.document.export_to_markdown()
        return markdown_text
    except Exception as e:
        print(f"Error parseando documento con Docling: {e}")
        return ""
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
