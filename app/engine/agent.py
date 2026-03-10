import json
from langchain.prompts import PromptTemplate
from langchain.chat_models import init_chat_model

import os
import re
import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate

def get_llm():
    try:
        os.environ["GOOGLE_API_KEY"] = "AIzaSyAnilUrCDdCD-kP0doz5fgpFHNsJ45sigw"
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0
        )
    except Exception as e:
        print(f"Error cargando el LLM Gemini: {e}")
        return None

def extract_form_data(markdown_text: str, json_form_schema: dict) -> dict:
    template = """
    Eres un analista experto en documentos legales mexicanos (Actas y Escrituras).
    Se te proporciona el documento extraído jerárquicamente en formato Markdown.
    También tienes el esquema del formulario dinámico JSON con los campos requeridos.
    
    TU TAREA PRINCIPAL:
    1. Extraer la información exacta del documento para rellenar los valores (`value`) de cada campo (`uuid`).
    2. MANEJO DE MATRICES/LISTAS: Si el esquema contiene bloques que representan colecciones (como un grupo de campos para 'Propietarios', 'Colindancias', etc.) y encuentras MÚLTIPLES incidencias en el documento:
       - Debes devolver una LISTA de objetos para ese bloque.
       - Cada objeto de la lista debe mantener los UUIDs originales pero con los valores específicos de esa incidencia.
    
    FORMA DE ENTREGA:
    Devuelve estrictamente un JSON puro donde las llaves sean los UUIDs y los valores sean los datos extraídos.
    Si un campo es parte de una lista repetible, el valor asociado al UUID del 'contenedor' o 'sección' debe ser la lista de objetos extraídos.
    Si un campo no se menciona en el documento, ponlo en nulo o cadena vacía.
    
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
