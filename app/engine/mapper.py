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
    Inyecta los datos extraídos directamente al campo `value` del JSON original.
    SOPORTE PARA MATRICES: Si un UUID de contenedor recibe una lista de objetos, 
    clona la estructura interna por cada incidencia.
    """
    import copy

    def _recurse_and_inject(node):
        if isinstance(node, dict):
            # 1. Caso estándar: Inyectar valor simple por UUID
            node_uuid = node.get("uuid")
            if node_uuid and node_uuid in extracted_data:
                val = extracted_data[node_uuid]
                
                # 2. Soporte MATRICES: Si el valor extraído es una lista, reestructuramos
                if isinstance(val, list) and ("controls" in node or "containers" in node):
                    original_controls = node.get("controls", [])
                    original_containers = node.get("containers", [])
                    
                    new_instances = []
                    for item_data in val:
                        # Clonamos la estructura para cada fila encontrada (ej: un propietario)
                        instance = {
                            "controls": copy.deepcopy(original_controls),
                            "containers": copy.deepcopy(original_containers)
                        }
                        # Inyectamos los datos específicos a esta nueva instancia clonada
                        _recurse_and_inject_simple(instance, item_data)
                        new_instances.append(instance)
                    
                    # Reemplazamos el contenido del nodo por la lista de instancias
                    node["instances"] = new_instances # Usamos una llave nueva para la colección
                else:
                    node["value"] = val

            # Continuar buscando en atributos anidados
            for v in node.values():
                _recurse_and_inject(v)
        elif isinstance(node, list):
            for item in node:
                _recurse_and_inject(item)

    def _recurse_and_inject_simple(node, data_map):
        """Helper para inyectar datos en una instancia clonada usando un mapa local."""
        if isinstance(node, dict):
            uid = node.get("uuid")
            if uid and uid in data_map:
                node["value"] = data_map[uid]
            for v in node.values():
                _recurse_and_inject_simple(v, data_map)
        elif isinstance(node, list):
            for item in node:
                _recurse_and_inject_simple(item, data_map)
                
    _recurse_and_inject(json_schema)
    return json_schema
