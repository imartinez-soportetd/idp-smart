import os
import re
import json
from core.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain.prompts import PromptTemplate

def get_llm():
    """
    Instancia el LLM configurado en Settings.
    Soporta Google (Gemini) y Ollama (Local).
    """
    try:
        if settings.llm_provider == "ollama":
            print(f"Conectando a LLM Local (Ollama) en {settings.ollama_base_url} con modelo {settings.ollama_model}...")
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
        print(f"Error cargando el LLM ({settings.llm_provider}): {e}")
        return None

def extract_form_data(markdown_text: str, json_form_schema: dict) -> dict:
    template = """
    Eres un analista experto en documentos legales mexicanos (Actas y Escrituras).
    Se te proporciona el documento extraído jerárquicamente en formato Markdown.
    También tienes el esquema del formulario dinámico JSON con los campos requeridos.
    
    TU TAREA PRINCIPAL:
    1. ANALIZAR PROFUNDAMENTE: El esquema JSON puede tener múltiples niveles de anidación (contenedores dentro de contenedores). Debes recorrer TODA la estructura, no solo el primer nivel.
    2. EXTRAER VALORES: Busca en el documento la información que corresponda a cada `uuid` del esquema y colócalo en el campo `value`.
    3. MANEJO DE MATRICES/LISTAS (CRÍTICO): Si encuentras una sección que es "Repetible" (ej: 'Propietarios', 'Antecedentes', 'Colindancias') y el documento menciona VARIAS de estas entidades:
       - El valor asociado al UUID del contenedor padre debe ser una LISTA de objetos.
       - Cada objeto en esa lista debe tener la estructura interna definida en el esquema (sus propios UUIDs) con los datos de esa instancia específica.
       - NO te limites a la primera coincidencia; extrae todas las que aparezcan en el documento.
    
    REGLAS DE FORMATO:
    - Retorna ÚNICAMENTE un JSON válido.
    - Las llaves deben ser los UUIDs.
    - Si un UUID corresponde a un contenedor con múltiples instancias, el valor es una lista `[]`.
    - Si un campo no existe en el documento, usa `null` o `""`.
    - Mantén la fidelidad de los datos (nombres exactos, fechas, montos).
    
    DOCUMENTO MARKDOWN:
    {document_md}
    
    ESQUEMA A EXTRAER (JSON):
    {form_schema}
    
    Respuesta (Solo JSON válido):
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
        return json.loads(clean_text)
    except Exception as e1:
        print(f"Intento 1 fallido de parseo LLM ({e1}). Buscando reparar el JSON cortado...")
        
        # Si el modelo cortó a la mitad, forzamos cerrar las llaves y comillas.
        # Buscamos la llave inicial
        start_idx = text_response.find('{')
        if start_idx != -1:
            json_str = text_response[start_idx:]
            # Limpiamos el último caracter si se cortó a la mitad de una línea o comilla
            json_str = re.sub(r'\"[^\"]*$', '"', json_str) # cierra comillas abiertas al final
            json_str = re.sub(r',\s*$', '', json_str)      # quita coma colgante al final
            
            # Forzamos cierre de llaves
            if not json_str.strip().endswith('}'):
                json_str += '\n}'
                
            try:
                return json.loads(json_str)
            except Exception as e2:
                print(f"Intento 2 de reparación fallido: {e2}")
                print(f"⚠️ RAW TEXT DEL MODELO (Falló):\n------\n{text_response}\n------")
                return {}
        else:
            print(f"No se encontró un bloque JSON en la respuesta.")
            print(f"⚠️ RAW TEXT DEL MODELO (Falló):\n------\n{text_response}\n------")
            return {}
