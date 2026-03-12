import os
import re
import json
from core.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate

def create_simplified_json(extracted_data: dict, schema: dict) -> dict:
    """
    Transforma uuid → value pairs a label → value pairs humanizados.
    NUNCA retorna null: siempre retorna un dict válido, aunque sea vacío.
    
    Este es SOLO un transformador de presentación, no cambia los datos.
    """
    simplified = {}
    uuid_to_label_map = {}
    
    # Fase 1: Construir mapa completo de uuid → label desde el esquema
    def build_uuid_map(node):
        """Recorre esquema y mapea uuid → label"""
        if isinstance(node, dict):
            uuid_val = node.get("uuid")
            label_val = node.get("label")
            if uuid_val and label_val:
                uuid_to_label_map[uuid_val] = label_val
            
            # Continuar en propiedades
            for v in node.values():
                build_uuid_map(v)
        elif isinstance(node, list):
            for item in node:
                build_uuid_map(item)
    
    build_uuid_map(schema)
    
    # Fase 2: Transformar datos extraídos usando el mapa
    def transform_value(value):
        """Convierte valor recursivamente: si es dict con uuids, substituye por labels"""
        if isinstance(value, dict):
            transformed = {}
            for k, v in value.items():
                # Si la clave es un uuid, usa su label
                label_key = uuid_to_label_map.get(k, k)
                transformed[label_key] = transform_value(v)
            return transformed
        elif isinstance(value, list):
            # Para arrays, transforma cada elemento
            return [transform_value(item) for item in value]
        else:
            # Valor primitivo
            return value
    
    # Fase 3: Inyectar datos transformados
    for uuid_key, value in extracted_data.items():
        label_key = uuid_to_label_map.get(uuid_key, uuid_key)
        transformed_value = transform_value(value)
        simplified[label_key] = transformed_value
    
    # Fase 4: Garantizar que NUNCA retorna None/null
    # Si está vacío, retorna estructura mínima válida
    if not simplified:
        simplified = {
            "Estado": "Sin datos extraídos del documento",
            "Nota": "Verifica que el documento contenga la información esperada"
        }
    
    return simplified

def get_llm():
    """
    Instancia el LLM configurado en Settings.
    Soporta Google (Gemini), Ollama (Legacy), y LocalAI (OpenAI Compatible).
    """
    try:
        if settings.llm_provider == "localai":
            print(f"🚀 Conectando a LocalAI en {settings.localai_base_url} con modelo {settings.localai_model}...")
            return ChatOpenAI(
                base_url=settings.localai_base_url,
                api_key="not-needed",  # LocalAI no requiere API key por defecto
                model=settings.localai_model,
                temperature=settings.localai_temperature,
                max_tokens=settings.localai_max_tokens,
                timeout=settings.localai_timeout,
                verbose=True
            )
        elif settings.llm_provider == "ollama":
            print(f"🔧 Conectando a LLM Local (Ollama) en {settings.ollama_base_url} con modelo {settings.ollama_model}...")
            return ChatOllama(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                temperature=0
            )
        else:
            # Por defecto usar Google Gemini
            if not settings.google_api_key:
                print("Error: No se ha configurado la GOOGLE_API_KEY.")
                return None
            os.environ["GOOGLE_API_KEY"] = settings.google_api_key
            return ChatGoogleGenerativeAI(
                model="gemini-flash-latest",
                temperature=0
            )
    except Exception as e:
        print(f"❌ Error cargando el LLM ({settings.llm_provider}): {e}")
        return None

def extract_form_data(markdown_text: str, json_form_schema: dict) -> dict:
    """
    Extrae datos legales de alta precisión mapeando TODOS los campos del esquema al documento.
    
    Retorna: dict con estructura uuid → value
    Cada UUID del esquema recibe su valor correspondiente del documento.
    """
    template = """
EXTRACCIÓN DE DATOS LEGALES CON MÁXIMA PRECISIÓN

Eres un experto en documentos legales mexicanos. Tu tarea es MAPEAR EXACTAMENTE cada UUID del esquema 
al valor correspondiente en el documento. NO inventes datos, NO simplifiques, NO agregues información.

INSTRUCCIONES CRÍTICAS:

1️⃣ LECTURA COMPLETA:
   - Lee TODA la información del documento
   - Si hay 3 solicitantes, TODOS deben extraerse (no solo el primero)
   - Si hay 2 titulares con porcentajes (20%, 80%), ambos deben aparecer
   - Busca TODOS los "Derechos de inscripción" (no solo el primero)

2️⃣ ESTRUCTURA DE RETORNO - UUID → VALUE:
   El JSON retornado tiene esta estructura EXACTA:
   {{
     "uuid-campo-simple": "valor_exacto",
     "uuid-campo-fecha": "YYYY-MM-DD",
     "uuid-campo-numero": 12345,
     "uuid-contenedor-repetible": [
       {{"uuid-sub1": "valor1", "uuid-sub2": "valor2"}},
       {{"uuid-sub1": "valor1b", "uuid-sub2": "valor2b"}},
       {{"uuid-sub1": "valor1c", "uuid-sub2": "valor2c"}}
     ]
   }}

3️⃣ MANEJO DE REPETIBLES (CRÍTICO):
   Si el esquema tiene un contenedor que aparece múltiples veces en el documento:
   - ¿3 solicitantes? → Retorna array con 3 objetos, cada uno con sus uuids
   - ¿2 titulares? → Retorna array con 2 objetos
   - ¿3 recibos de derechos? → Retorna array con 3 objetos
   
   SIEMPRE que haya múltiples instancias, retorna un ARRAY, no un objeto único.

4️⃣ VALORES EXACTOS:
   - Nombres: EXACTOS como aparecen (respeta MAYÚSCULAS/minúsculas)
   - Fechas: Convierte a YYYY-MM-DD (ej: "1995-09-28")
   - Montos: Solo número sin $ ni comas (ej: 41540)
   - Porcentajes: Solo número (ej: 20, 40, 80 - SIN símbolo %)
   - Estados/Municipios: Exacto como en documento
   - Selecciones (SI/NO, estado civil): Exacto del documento

5️⃣ VALIDACIÓN LÓGICA:
   - Si hay titular 1 con 20%, busca dónde están los otros 80%
   - Si hay 3 solicitantes, debe haber registro de todos (revisión cruzada en documento)
   - Suma de porcentajes: 3 titulares → sus % deben sumar 100%
   - Fechas coherentes: inscripción ≥ fecha escritura

6️⃣ MANEJO DE AUSENCIAS:
   - Si un campo NO existe en el documento → usa null (NO strings vacíos)
   - Si faltan datos → null, no inventes
   - Si está parcialmente legible → usa lo legible, marca lo dudoso con "?"

ESQUEMA (estructura y UUIDs):
{form_schema}

DOCUMENTO:
{document_md}

⚠️ RESTRICCIONES FINALES:
- Retorna SOLO JSON válido
- Sin explicaciones, sin markdown, sin backticks
- Respeta EXACTAMENTE la estructura uuid → value del esquema
- Si un uuid no existe en el documento → omítelo O usa null
- Arrays SIEMPRE para campos repetibles (incluso si hay solo 1 instancia)

Respuesta (Solo JSON):
"""
    
    llm = get_llm()
    if not llm:
        print("LangChain LLM no configurado. Regresando dummy response.")
        return {}
        
    prompt = PromptTemplate.from_template(template)
    chain = prompt | llm
    
    safe_markdown = markdown_text[:1000000] 
    
    response = chain.invoke({
        "document_md": safe_markdown,
        "form_schema": json.dumps(json_form_schema, indent=2)
    })
    
    text_response = response.content.strip()
    clean_text = text_response.replace('```json', '').replace('```', '').strip()
    
    try:
        extracted_json = json.loads(clean_text)
        return extracted_json
    except Exception as e1:
        print(f"❌ Intento 1 fallido de parseo LLM ({e1}). Intentando reparar...")
        
        # Si el modelo cortó a la mitad, forzamos cerrar las llaves y comillas.
        start_idx = text_response.find('{')
        if start_idx != -1:
            json_str = text_response[start_idx:]
            
            # Estrategia de reparación: contar llaves y arrays, cerrar lo que falta
            open_braces = json_str.count('{') - json_str.count('}')
            open_brackets = json_str.count('[') - json_str.count(']')
            open_quotes = len(re.findall(r'(?<!\\)"', json_str)) % 2  # detecta comillas desemparejadas
            
            # Limpiar caracteres cortados
            json_str = re.sub(r'["}\]]\s*$', '', json_str)  # quita caracteres incompletos al final
            
            # Cerrar lo que falta
            if open_quotes:
                json_str += '"'
            if open_brackets > 0:
                json_str += ']' * open_brackets
            if open_braces > 0:
                json_str += '}' * open_braces
                
            try:
                extracted_json = json.loads(json_str)
                print(f"✅ JSON reparado exitosamente")
                return extracted_json
            except Exception as e2:
                print(f"❌ Intento 2 de reparación fallido: {e2}")
                print(f"⚠️ RAW TEXT DEL MODELO:\n------\n{text_response[:500]}\n------")
                return {}
        else:
            print(f"❌ No se encontró un bloque JSON en la respuesta.")
            print(f"⚠️ RAW TEXT DEL MODELO:\n------\n{text_response[:500]}\n------")
            return {}
