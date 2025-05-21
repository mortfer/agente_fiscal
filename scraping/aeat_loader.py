# utils/hacienda_loader.py
from pathlib import Path
import requests, bs4
from urllib.parse import urljoin
from langchain.docstore.document import Document
import re

def normalizar_espacios(texto):
    return (texto.replace("\xa0", " ")     # nbsp
                 .replace("\u200b", "")     # zero-width
                 .replace("\u202f", " ")    # narrow space
                 .replace("\u00ad", "")     # soft hyphen
            )
def limpiar_pdf_widget(texto: str) -> str:
    frases_basura = [
        "\nGenerar PDF Cerrar La generación del PDF puede tardar varios minutos dependiendo de la cantidad de información. Seleccione la información que desee incluir en el PDF: Página actual Apartado actual y subapartados Todo el documento Puede cancelar la generación del PDF en cualquier momento. Cancelar Continuar",
    ]
    for frase in frases_basura:
        texto = texto.replace(frase, "")
    return texto.strip()

    
def extraer_subapartados(soup, categoria, url, ccaa):
    secciones = []
    main = soup.select_one("main")

    current_title = "Introducción"
    current_content = []

    for elem in main.children:
        if elem.name in ["h2", "h3"]:
            if current_content:
                contenido = limpiar_pdf_widget("\n".join(current_content))
                if contenido:
                    secciones.append((current_title, contenido))

                current_content = []
            current_title = elem.get_text(" ", strip=True)
            current_title = normalizar_espacios(current_title)
        elif elem.name:
            text = elem.get_text(" ", strip=True)
            text = normalizar_espacios(text)
            if text:
                current_content.append(text)

    if current_content:
        contenido = limpiar_pdf_widget("\n".join(current_content))
        if contenido:
            secciones.append((current_title, contenido))

    return [
        Document(
            page_content=content,
            metadata={
                "ccaa": ccaa,
                "categoria": categoria,
                "subapartado": titulo,
                "url": url
            }
        )
        for titulo, content in secciones
    ]

class HaciendaLoader:
    BASE = ("https://sede.agenciatributaria.gob.es/Sede/ayuda/"
            "manuales-videos-folletos/manuales-practicos/"
            "irpf-2024-deducciones-autonomicas/")

    def __init__(self, ccaa_slug="comunitat-valenciana"):
        self.index_url = urljoin(self.BASE, f"{ccaa_slug}.html")
        self.ccaa = ccaa_slug.replace("-", " ").title()

    def load(self):
        docs = []
        lista_deducciones = []
        index_html = requests.get(self.index_url, timeout=20)
        index_html.encoding = "utf-8"   
        soup = bs4.BeautifulSoup(index_html.text, "lxml")

        for a in soup.select("main a[href$='.html']"):
            href = a["href"]
            full_url = urljoin(self.index_url, href)
            # slug = Path(href).stem # No se usa slug aquí directamente
            categoria = a.get_text(" ", strip=True)
            categoria = normalizar_espacios(categoria)
            lista_deducciones.append(categoria) # Guardamos el título de la deducción

            resp = requests.get(full_url, timeout=20)
            resp.encoding = "utf-8"      
            soup2 = bs4.BeautifulSoup(resp.text, "lxml")

            docs.extend(
                extraer_subapartados(soup2, categoria=categoria, url=full_url, ccaa=self.ccaa)
            )
        return docs, lista_deducciones
