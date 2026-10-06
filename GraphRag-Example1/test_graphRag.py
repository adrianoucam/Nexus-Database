import json
import os
import math
import urllib.request
import urllib.error

URL = os.environ.get("NEXUSDB_TEST_URL", "http://127.0.0.1:7474/db/data/cypher")
DATABASE = os.environ.get("NEXUSDB_TEST_DATABASE", "VECTOR_TEST")
USER = os.environ.get("NEXUSDB_TEST_USER", "administrador2")
PASSWORD = os.environ.get("NEXUSDB_TEST_PASSWORD", "senha1234567890")


def cypher(query):
    payload = {
        "statements": [
            {"query": query}
        ]
    }

    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-User": USER,
            "X-Pass": PASSWORD,
            "X-Database": DATABASE,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if result.get("errors") or result.get("status") != "success":
                raise AssertionError("NexusDB retornou erro de consulta")
            return result

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"HTTP ERROR {e.code}")
        print(body)
        raise


def check(condition, message):
    if condition:
        print(f"[OK] {message}")
    else:
        print(f"[ERRO] {message}")
        raise AssertionError(message)


print("=" * 70)
print("NexusDB Vector/HNSW - teste funcional")
print("=" * 70)

# -------------------------------------------------------
# 1. Criar pequenos embeddings de dimensão 4
# -------------------------------------------------------

print("\n[1] Criando nós...")

cypher("""
CREATE (:Chunk {
    nome: 'Rust',
    texto: 'Rust é uma linguagem de programação de sistemas',
    embedding: [1.0, 0.0, 0.0, 0.0]
})
""")

cypher("""
CREATE (:Chunk {
    nome: 'NexusDB',
    texto: 'NexusDB é um banco de dados de grafos escrito em Rust',
    embedding: [0.95, 0.05, 0.0, 0.0]
})
""")

cypher("""
CREATE (:Chunk {
    nome: 'Python',
    texto: 'Python é uma linguagem usada em ciência de dados',
    embedding: [0.0, 1.0, 0.0, 0.0]
})
""")

cypher("""
CREATE (:Chunk {
    nome: 'Biologia',
    texto: 'Proteínas interagem em redes biológicas',
    embedding: [0.0, 0.0, 1.0, 0.0]
})
""")

cypher("""
CREATE (:Chunk {
    nome: 'Geografia',
    texto: 'Coordenadas representam posições geográficas',
    embedding: [0.0, 0.0, 0.0, 1.0]
})
""")

# -------------------------------------------------------
# 2. Criar índice HNSW
# -------------------------------------------------------

print("\n[2] Criando índice HNSW...")

result = cypher("""
CALL vector.createIndex(
    'chunk_embeddings',
    'Chunk',
    'embedding',
    4,
    'cosine'
)
""")

# -------------------------------------------------------
# 3. Listar índices
# -------------------------------------------------------

print("\n[3] Listando índices...")

result = cypher("""
CALL vector.listIndexes()
""")

# -------------------------------------------------------
# 4. Busca vetorial
# -------------------------------------------------------

print("\n[4] Busca por vetor próximo de Rust/NexusDB...")

result = cypher("""
CALL vector.search(
    'chunk_embeddings',
    [1.0, 0.0, 0.0, 0.0],
    3,
    32
)
""")

# -------------------------------------------------------
# 5. Verificação básica do resultado
# -------------------------------------------------------

statement_result = None

if isinstance(result, dict):
    resultados = result.get("resultados", [])

    # dependendo do envelope HTTP do NexusDB
    if resultados:
        if isinstance(resultados[0], dict) and "resultados" in resultados[0]:
            statement_result = resultados[0]
        else:
            statement_result = result

if statement_result:
    hits = statement_result.get("resultados", [])

    check(len(hits) > 0, "A busca retornou resultados")

    print("\nRanking:")

    for i, hit in enumerate(hits, 1):
        node = hit.get("node", {})
        props = node.get("properties", {})

        print(
            f"{i:2} | "
            f"{props.get('nome')} | "
            f"score={hit.get('score')} | "
            f"distance={hit.get('distance')}"
        )

else:
    raise AssertionError("Envelope sem resultados vetoriais")

print("\n" + "=" * 70)
print("TESTE FINALIZADO")
print("=" * 70)