import json
from langchain.prompts import PromptTemplate
from langchain.chat_models import init_chat_model

def get_llm():
    # En producción esto apuntaría a un LLM Hosteado (Ej: Llama 3 o gpt-4o)
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(temperature=0, model="gpt-4o-mini")
    except ImportError:
        # Fallback simple para cuando no hay llaves
        return None

def extract_form_data(markdown_text: str, json_form_schema: dict) -> dict:
    """
    Toma el texto Markdown (de Docling) y lo inyecta a LangChain para mapear
    los labels de `json_form_schema` buscando llenar el campo `value` correspondiente
    por UUID.
    """
    
    # Prompting Semántico
    template = """
    Eres un analista experto en documentos legales mexicanos (Actas y Escrituras).
    Se te proporciona el documento extraído jerárquicamente en formato Markdown por Granite VLM.
    También tienes el esquema del formulario dinámico JSON con los campos requeridos (`labels`).
    
    Tu tarea: Extraer la información exacta del documento para rellenar los valores (`value`)
    de cada campo requerido en el JSON.
    Devuelve estrictamente un JSON puro que contenga los "UUIDs" como llave y el valor extraído como valor.
    Si un campo no se menciona en el documento, ponlo en nulo o cadena vacía, pero respeta el dict.

    DOCUMENTO MARKDOWN:
    {document_md}
    
    ESQUEMA A EXTRAER (JSON):
    {form_schema}
    
    Respuesta (Solo JSON válido):
    """
    
    llm = get_llm()
    if not llm:
        print("LangChain LLM no configurado. Regresando dummy response.")
        
        # Mapeo dummy simulando que extrajo los valores correctos
        dummy_result = {}
        for item in json_form_schema:  # Suponiendo que json_form_schema es una lista de dicts
            uuid = item.get("uuid", "unknown_id")
            label = item.get("label", "Desconocido")
            dummy_result[uuid] = f"<Dato extraído por IA para: {label}>"
        return dummy_result
        
    prompt = PromptTemplate.from_template(template)
    chain = prompt | llm
    
    # Prevenimos exceder límite de tokens trivialmente cortando a 25k chars
    safe_markdown = markdown_text[:25000] 
    
    response = chain.invoke({
        "document_md": safe_markdown,
        "form_schema": json.dumps(json_form_schema, indent=2)
    })
    
    # Parsear respuesta limpia
    text_response = response.content.replace('```json', '').replace('```', '')
    try:
        return json.loads(text_response)
    except Exception as e:
        print(f"Error parseando resultado de LLM: {e}")
        return {"error": "Failed to parse"}
