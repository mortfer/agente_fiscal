import json
from pathlib import Path
from aeat_loader import HaciendaLoader

# Comunidades a scrapear (usa los slugs del sitio web)
CCAA_SLUGS = [
    "comunitat-valenciana",
    "comunidad-autonoma-andalucia",
    "comunidad-autonoma-cataluna",
    "comunidad-madrid"
]

DATA_DIR = Path("scraping/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Diccionario para guardar el índice de deducciones por CCAA
deducciones_por_ccaa = {}

for slug in CCAA_SLUGS:
    output_path = DATA_DIR / f"{slug}.jsonl"
    
    print(f"Procesando {slug.replace('-', ' ').title()}...")
    loader = HaciendaLoader(slug)
    try:
        # Siempre cargamos para obtener la lista de deducciones
        docs, lista_nombres_deducciones = loader.load()
        deducciones_por_ccaa[slug] = lista_nombres_deducciones

    except Exception as e:
        print(f"Error al cargar datos para {slug}: {e}")
        # Si hay un error al cargar, no podemos obtener la lista de deducciones para esta CCAA
        # Es importante decidir cómo manejar esto. Por ahora, continuamos.
        # Podríamos añadir un placeholder o simplemente omitirla del índice.
        deducciones_por_ccaa[slug] = [] # Opcional: añadir lista vacía si falla
        continue

    # Solo escribimos el archivo .jsonl si no existe o si está vacío y tenemos documentos
    if not output_path.exists() or (output_path.stat().st_size == 0 and docs):
        if not docs:
            print(f"No se generaron documentos para {slug} (loader.load() no devolvió docs). No se creará {output_path.name}.")
        else:
            print(f"Scrapeando y guardando {slug.replace('-', ' ').title()} en {output_path.name}...")
            with output_path.open("w", encoding="utf-8") as f:
                for d in docs:
                    json.dump({
                        "content": d.page_content,
                        "metadata": d.metadata
                    }, f, ensure_ascii=False)
                    f.write("\n")
            print(f"Guardado: {output_path.name} ({len(docs)} documentos)\n")
    elif docs: # Si el archivo existe y tenemos documentos (aunque no vayamos a sobreescribir)
        print(f"Ya existe: {output_path.name}. No se sobrescribe. Se usaron {len(docs)} documentos para el índice.\n")
    else: # Si el archivo existe pero no obtuvimos documentos (raro si load tuvo éxito antes)
         print(f"Ya existe: {output_path.name} y no se obtuvieron nuevos documentos. No se sobrescribe.\n")

# Guardar el índice de deducciones en un archivo JSON
indice_deducciones_path = DATA_DIR / "deducciones_por_ccaa.json"
with indice_deducciones_path.open("w", encoding="utf-8") as f_index:
    json.dump(deducciones_por_ccaa, f_index, ensure_ascii=False, indent=2)

print(f"Guardado índice de deducciones: {indice_deducciones_path.name}")

