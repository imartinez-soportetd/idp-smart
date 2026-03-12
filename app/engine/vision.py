import os
import tempfile
from core.minio_client import get_minio_client
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    AcceleratorOptions,
    AcceleratorDevice,
)

def extract_markdown_from_minio(object_name: str) -> str:
    """
    Descarga el documento de MinIO temporalmente y utiliza Docling (Granite-Docling)
    para convertir el documento jerárquico y sus tablas en Markdown puro.
    Optimizado para usar CUDA si hay una GPU NVIDIA disponible (Docling >= 2.10 API).
    """
    client = get_minio_client()

    # Configurar opciones de acelerador para GPU (API correcta de Docling 2.x)
    try:
        import torch
        if torch.cuda.is_available():
            device = AcceleratorDevice.CUDA
            device_name = torch.cuda.get_device_name(0)
            print(f"Vision Engine: Usando GPU ({device_name}) para procesamiento Docling.")
        else:
            device = AcceleratorDevice.CPU
            print("Vision Engine: GPU no detectada, usando CPU para procesamiento Docling.")
    except Exception:
        device = AcceleratorDevice.AUTO
        print("Vision Engine: torch no disponible, usando modo AUTO.")

    accelerator_options = AcceleratorOptions(device=device)
    pipeline_options = PdfPipelineOptions(
        accelerator_options=accelerator_options,
        do_ocr=True,
        do_table_structure=True,
    )

    # Inicializar el convertidor con las opciones de aceleración
    doc_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: pipeline_options
        }
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        client.fget_object("idp-documents", object_name, tmp_file.name)
        tmp_path = tmp_file.name

    try:
        # Procesar el documento
        result = doc_converter.convert(tmp_path)
        markdown_text = result.document.export_to_markdown()
        return markdown_text
    except Exception as e:
        print(f"Error parseando documento con Docling: {e}")
        import traceback
        traceback.print_exc()
        return ""
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
