from core.minio_client import get_minio_client
import json

def get_json_schema(bucket: str, object_name: str) -> dict:
    """Extrae el JSON subido al endpoint para saber qué buscar del documento."""
    client = get_minio_client()
    try:
        response = client.get_object(bucket, object_name)
        data = response.read()
        return json.loads(data.decode("utf-8"))
    except Exception as e:
        print(f"Error descargando el JSON del bucket {bucket}/{object_name}: {e}")
        return []
    finally:
        if 'response' in locals():
            response.close()
            response.release_conn()

def map_results_to_json(json_schema: dict, extracted_data: dict) -> dict:
    """
    Inyecta los datos extraídos (diccionario con uuid -> valor)
    directamente al campo `value` del JSON original.
    """
    for entry in json_schema:
        if isinstance(entry, dict) and "uuid" in entry:
            uid = entry["uuid"]
            if uid in extracted_data:
                entry["value"] = extracted_data[uid]
                
    return json_schema
