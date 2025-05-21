from dotenv import load_dotenv
load_dotenv()
import os, json
from pathlib import Path
import sys
import threading 
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
from langchain_community.vectorstores import FAISS
from langchain_community.tools import TavilySearchResults 
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
#from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.tools import tool
from typing import Union, List, Optional 

DB_DIR = "/db"  
_vectorstore = None
_retriever = None
_lock = threading.Lock()

def get_retriever(search_kwargs={"k": 5}):
    global _vectorstore, _retriever
    if _retriever is None:
        with _lock:
            if _retriever is None:  
                try:   
                    embeddings = OllamaEmbeddings(
                        model=os.getenv("EMBEDDING_MODEL"),
                        base_url=os.getenv("OLLAMA_HOST")
                    )      
                    _vectorstore = FAISS.load_local(
                        DB_DIR,
                        embeddings,
                        allow_dangerous_deserialization=True
                    )
                    _retriever = _vectorstore.as_retriever(search_kwargs=search_kwargs)
                    print(f"FAISS index loaded successfully from {DB_DIR}.")
                except Exception as e:
                    print(f"CRITICAL: Failed to load FAISS index from {DB_DIR}. Error: {e}")
                    raise  
    return _retriever

DEDUCCIONES_DATA_PATH = project_root / "scraping" / "data" / "deducciones_por_ccaa.json"
DEDUCCIONES_POR_CCAA = {}
try:
    with open(DEDUCCIONES_DATA_PATH, 'r', encoding='utf-8') as f:
        DEDUCCIONES_POR_CCAA = json.load(f)
except:
    print(f"ADVERTENCIA: Error al intentar cargar {DEDUCCIONES_DATA_PATH}")
    DEDUCCIONES_POR_CCAA = {}
VALID_SLUGS = list(DEDUCCIONES_POR_CCAA.keys())
SLUGS_DESCRIPTION = ", ".join([f"'{s}'" for s in VALID_SLUGS]) if VALID_SLUGS else "No hay slugs cargados."

@tool
def regional_tax_deductions_details(query: str) -> str:
    """Busca fragmentos relevantes sobre deducciones autonómicas específicas cuando necesitas detalles como el importe, los requisitos, compatibilidad, etc. Proporciona la consulta de búsqueda como argumento."""
    retriever = get_retriever()  
    docs = retriever.invoke(query)
    if not docs:
        return "No se han encontrado documentos relevantes para esa consulta."
    return "\n\n".join(f"* {doc.page_content}" for doc in docs)

@tool(
    description="""Proporciona una lista de los nombres de las deducciones fiscales disponibles para una o varias comunidades autónomas (CCAA) de España.
    El argumento 'ccaa_slugs' debe ser el identificador (slug) de la CCAA o una lista de slugs.
    Los slugs válidos actualmente cargados son: {slugs}. Es preferible usar esta herramienta a {name}.
    """.format(slugs=SLUGS_DESCRIPTION, name=str(regional_tax_deductions_details))
)
def list_regional_tax_deductions(ccaa_slugs: Union[str, List[str]]) -> str: 
    if not DEDUCCIONES_POR_CCAA:
        return "No hay datos de deducciones autonómicas cargados. Verifica la configuración del scraper."

    if isinstance(ccaa_slugs, str):
        slugs_to_process = [ccaa_slugs]
    elif isinstance(ccaa_slugs, list):
        slugs_to_process = ccaa_slugs
    else:
        return "Argumento 'ccaa_slugs' inválido. Debe ser un string o una lista de strings."
    results = []
    for slug in slugs_to_process:
        if slug in DEDUCCIONES_POR_CCAA:
            deducciones = DEDUCCIONES_POR_CCAA[slug]
            if deducciones:
                result_str = f"Deducciones para '{slug}':\n"
                result_str += "\n".join([f"- {d}" for d in deducciones])
                results.append(result_str)
            else:
                results.append(f"No se encontraron deducciones listadas para '{slug}'.")
        else:
            results.append(f"El slug '{slug}' no es válido o no se encontraron datos. Los slugs válidos son: {SLUGS_DESCRIPTION}")
    
    if not results: 
        return f"No se especificaron slugs de CCAA para procesar. Los slugs válidos son: {SLUGS_DESCRIPTION}"

    return "\n\n".join(results)

@tool
def internet_search_tool(query: str) -> str:
    """Realiza una búsqueda en internet. Se recomienda usarlo solo como último recurso si el resto de herramientas no dan los resultados deseados. 
    """
    ALLOWED_SEARCH_DOMAINS: List[str] = ["https://declarando.es/", "https://sede.agenciatributaria.gob.es/", "https://taxdown.es/", "https://taxscouts.es/"]

    if not os.getenv("TAVILY_API_KEY"):
        return "Error: La variable de entorno TAVILY_API_KEY no está configurada. Esta herramienta no puede funcionar."
    
    search_kwargs = {}
    if ALLOWED_SEARCH_DOMAINS: 
        search_kwargs['include_domains'] = ALLOWED_SEARCH_DOMAINS
        
    try:
        tavily_tool = TavilySearchResults(max_results=3, **search_kwargs)
        search_results = tavily_tool.invoke({"query": query})
        if isinstance(search_results, list) and all(isinstance(item, dict) for item in search_results):
             formatted_results = []
             for i, res in enumerate(search_results): 
                 title = res.get('title', 'N/A')
                 url = res.get('url', 'N/A')
                 content_snippet = res.get('content', 'N/A')[:250] + "..." 
                 formatted_results.append(f"Resultado {i+1}:\nTitulo: {title}\nURL: {url}\nFragmento: {content_snippet}")
             return "\n\n".join(formatted_results) if formatted_results else "No se encontraron resultados."
        elif isinstance(search_results, str): 
            return search_results
        else:
            return "Formato de resultados de búsqueda inesperado."
    except Exception as e:
        return f"Error durante la búsqueda en internet: {str(e)}" 