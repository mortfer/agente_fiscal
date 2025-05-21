import json
from pathlib import Path
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter, CharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import FastEmbedEmbeddings, OllamaEmbeddings
from transformers import AutoTokenizer
import sys
import os
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
MAX_TOKENS_TOTAL = os.getenv("MAX_TOKENS_TOTAL")
DATA_DIR = Path("scraping/data")
OUTPUT_DIR = Path("db/")

tokenizer = AutoTokenizer.from_pretrained('mixedbread-ai/mxbai-embed-large-v1')
embedder = OllamaEmbeddings(model=EMBEDDING_MODEL)

# Configuración global

CHUNK_OVERLAP = 64

def build_prefijo(metadata: dict) -> str:
    return (
        f"[CCAA: {metadata['ccaa']}]"
        f"[Categoría: {metadata['categoria']}]"
        f"[Subapartado: {metadata.get('subapartado', '')}]"
    )

def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False))

def split_with_prefijo_tokenizado(doc: Document) -> list[Document]:
    prefijo = build_prefijo(doc.metadata)
    n_tokens_prefijo = count_tokens(prefijo)

    # Chunk size máximo posible para el contenido
    chunk_size = max(32, MAX_TOKENS_TOTAL - n_tokens_prefijo)

    splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        tokenizer=tokenizer,
        chunk_size=chunk_size,
        chunk_overlap=CHUNK_OVERLAP
    )

    sub_chunks = splitter.split_text(doc.page_content)
    # if len(sub_chunks)>1:
    #     print("-" * 50)
    #     print(prefijo)
    #     for chunk in sub_chunks:
    #         page_content=f"{prefijo}\n{chunk}"
    #         print(page_content)
    #         print(f"TOKENS: {count_tokens(page_content)}")
        
    return [
        Document(
            page_content=f"{prefijo}\n{chunk}",
            metadata=doc.metadata
        )
        for chunk in sub_chunks
    ]

for jsonl_path in DATA_DIR.glob("*.jsonl"):
    ccaa_slug = jsonl_path.stem
    output_path = OUTPUT_DIR 
    

    with jsonl_path.open(encoding="utf-8") as f:
        raw_docs = [json.loads(line) for line in f]

    documents = [Document(page_content=d["content"], metadata=d["metadata"])
                 for d in raw_docs]

    # aplicar splitter dentro de cada subapartado (si necesario)
    chunks = []
    for doc in documents:
        chunks.extend(split_with_prefijo_tokenizado(doc))
    for chunk in chunks[:2]:
        print("-" * 50)
        print(chunk.page_content)
        print(f"TOKENS: {count_tokens(chunk.page_content)}")

    print(f"🔧 {ccaa_slug}: {len(documents)} docs → {len(chunks)} chunks")
    
    if output_path.exists():
        vs = FAISS.load_local(str(output_path), embedder, allow_dangerous_deserialization=True)
        vs.add_documents(chunks)
    else:
        vs = FAISS.from_documents(chunks, embedder)
    
    vs.save_local(str(output_path))

    print(f"✅ FAISS guardado en {output_path}\n")
