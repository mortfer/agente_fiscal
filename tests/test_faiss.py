import pytest
from langchain.vectorstores.base import VectorStoreRetriever
from langchain.docstore.document import Document
from ingest.load_faiss import load_vectorstore 

@pytest.fixture(scope="module")
def vectorstore():
    return load_vectorstore("db/")

#TODO: test que compruebe que hay al menos un elemento de cada cccaa

def test_valenciana_filter(vectorstore):
    query = "deducciones fiscales de comunidad valenciana"
    results = vectorstore.similarity_search(query, k=8)
    assert all("valenciana" in d.metadata["ccaa"].lower() for d in results)

def test_donaciones_valencia(vectorstore):
    query = "hay deducciones por donaciones en madrid?"
    results = vectorstore.similarity_search(query, k=5)
    assert any(
        "donac" in d.page_content.lower() and d.metadata.get("ccaa") == "Comunidad Madrid"
        for d in results
    )

def test_max_distance(vectorstore):
    query = "deducciones en comunidad de madrid"
    results = vectorstore.similarity_search_with_score(query, k=5)
    max_distance = 235
    assert all(score < max_distance for _, score in results)
    
def test_metadata_fields_present(vectorstore):
    query = "deducciones por vivienda"
    results = vectorstore.similarity_search(query, k=5)
    for d in results:
        assert "ccaa" in d.metadata
        assert "categoria" in d.metadata
        
