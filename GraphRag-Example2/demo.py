"""
Demo reproduzível do NexusDB:
HNSW + busca vetorial exata + GraphRAG.

Objetivos:
1. Gerar dataset sintético de pedidos.
2. Gerar embeddings TF-IDF localmente.
3. Importar o Property Graph no NexusDB.
4. Criar índice vetorial HNSW.
5. Comparar HNSW com busca exata.
6. Medir Recall@K.
7. Executar GraphRAG sobre os resultados vetoriais.
8. Diagnosticar diferenças entre HNSW e brute-force.
9. Gerar relatório JSON e HTML.

Somente biblioteca padrão do Python.
"""

import argparse
from collections import Counter
from datetime import datetime
import getpass
import html
import json
import math
import os
from pathlib import Path
import re
import statistics
import time
import unicodedata
import urllib.error
import urllib.request
import uuid


SOURCE = (
    "https://memgraph.com/blog/"
    "graphrag-vs-standard-rag-success-stories"
)


# ============================================================
# DATASET
# ============================================================

def dataset():

    nodes = []
    edges = []

    def node(key, label, **props):
        nodes.append(
            {
                "key": key,
                "label": label,
                "properties": {
                    "external_id": key,
                    "simulado": True,
                    **props,
                },
            }
        )

    def edge(a, b, kind):
        edges.append(
            {
                "from_key": a,
                "to_key": b,
                "type": kind,
                "properties": {
                    "fonte": "gerador deterministico v1"
                },
            }
        )

    # --------------------------------------------------------
    # Fornecedores + componentes
    # --------------------------------------------------------

    for i in range(20):

        node(
            f"FOR-{i:02}",
            "Fornecedor",
            nome=f"Fornecedor Simulado {i:02}",
            regiao=[
                "Sul",
                "Sudeste",
                "Nordeste",
                "Centro-Oeste",
            ][i % 4],
        )

        node(
            f"CMP-{i:02}",
            "Componente",
            nome=f"Controlador industrial C{i:02}",
        )

        edge(
            f"CMP-{i:02}",
            f"FOR-{i:02}",
            "FORNECIDO_POR",
        )

    # --------------------------------------------------------
    # Clientes
    # --------------------------------------------------------

    for i in range(30):

        node(
            f"CLI-{i:02}",
            "Cliente",
            nome=f"Industria Ficticia {i:02}",
        )

    # --------------------------------------------------------
    # Causas simuladas
    # --------------------------------------------------------

    causes = [

        (
            "qualidade",
            "Inspecao detectou solda fora da tolerancia",
            "Refazer solda e reinspecionar",
            3,
        ),

        (
            "material",
            "Remessa de componente chegou incompleta",
            "Solicitar reposicao do componente",
            5,
        ),

        (
            "transporte",
            "Transportadora remarcou a coleta",
            "Agendar coleta alternativa",
            2,
        ),

        (
            "manutencao",
            "Equipamento da linha entrou em manutencao",
            "Realocar montagem para outra linha",
            4,
        ),
    ]

    # --------------------------------------------------------
    # Pedidos
    # --------------------------------------------------------

    for i in range(120):

        order = f"PED-{1000+i}"
        lot = f"LOT-{i:03}"
        event = f"EVT-{i:03}"
        doc = f"DOC-{i:03}"

        category, cause, action, delay = causes[i % 4]

        node(
            order,
            "Pedido",
            codigo=order,
            status="atrasado",
            quantidade=100 + i * 7,
        )

        node(
            lot,
            "Lote",
            codigo=lot,
            linha=f"LINHA-{i % 6}",
        )

        node(
            event,
            "Ocorrencia",
            categoria=category,
            causa=cause,
            acao=action,
            atraso_dias=delay,
            referencia=f"LOG-{i:03}",
        )

        node(
            doc,
            "Chunk",
            titulo=f"Atendimento do pedido {order}",
            texto=(
                f"O pedido {order} tem uma solicitacao de "
                f"atendimento sobre atraso na entrega. "
                f"Consulte o lote de producao e os registros "
                f"operacionais para obter a justificativa."
            ),
        )

        edge(
            doc,
            order,
            "REFERE_SE_A",
        )

        edge(
            order,
            lot,
            "PRODUZIDO_NO",
        )

        edge(
            order,
            f"CLI-{i % 30:02}",
            "SOLICITADO_POR",
        )

        edge(
            lot,
            event,
            "TEM_OCORRENCIA",
        )

        edge(
            lot,
            f"CMP-{i % 20:02}",
            "UTILIZA",
        )

    # --------------------------------------------------------
    # Chunks genéricos
    # --------------------------------------------------------

    topics = [
        "prazo de entrega",
        "qualidade da solda",
        "transporte de pedidos",
        "reposicao de material",
    ]

    for i in range(60):

        node(
            f"MAN-{i:03}",
            "Chunk",
            titulo=f"Procedimento geral {i:03}",
            texto=(
                f"Manual {i:03}: orientacoes gerais sobre "
                f"{topics[i % 4]}. "
                f"O atendimento deve consultar registros "
                f"antes de informar a causa de um atraso."
            ),
        )

    return nodes, edges


# ============================================================
# TOKENIZAÇÃO
# ============================================================

def tokens(text):

    clean = "".join(
        c
        for c in unicodedata.normalize(
            "NFKD",
            text.lower(),
        )
        if not unicodedata.combining(c)
    )

    return re.findall(
        r"[a-z0-9]+(?:-[a-z0-9]+)*",
        clean,
    )


# ============================================================
# TF-IDF
# ============================================================

class Tfidf:

    def __init__(self, texts):

        frequency = Counter(
            word
            for text in texts
            for word in set(tokens(text))
        )

        self.vocabulary = sorted(frequency)

        self.idf = {
            word:
            math.log(
                (1 + len(texts))
                /
                (1 + frequency[word])
            ) + 1
            for word in self.vocabulary
        }

    def encode(self, text):

        counts = Counter(tokens(text))

        vector = [

            (
                (1 + math.log(counts[word]))
                * self.idf[word]
            )
            if counts[word]
            else 0.0

            for word in self.vocabulary
        ]

        norm = math.sqrt(
            sum(x * x for x in vector)
        )

        if not norm:
            raise ValueError(
                "Pergunta sem termos presentes no corpus"
            )

        return [
            round(x / norm, 9)
            for x in vector
        ]


# ============================================================
# CLIENTE NEXUSDB
# ============================================================

class Client:

    def __init__(
        self,
        url,
        user,
        password,
        database,
    ):

        self.url = url.rstrip("/")
        self.user = user
        self.password = password
        self.database = database

    def post(
        self,
        route,
        payload,
    ):

        request = urllib.request.Request(

            self.url + route,

            json.dumps(payload).encode(),

            {
                "Content-Type":
                    "application/json",

                "X-User":
                    self.user,

                "X-Pass":
                    self.password,

                "X-Database":
                    self.database,
            },
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=120,
            ) as response:

                result = json.load(response)

        except urllib.error.HTTPError as error:

            if error.code == 401:

                raise RuntimeError(
                    "HTTP 401: confira usuario/senha "
                    "e bloqueio. Nenhuma nova tentativa "
                    "automatica sera feita."
                ) from None

            raise RuntimeError(
                f"HTTP {error.code}: "
                f"{error.read().decode(errors='replace')}"
            ) from None

        if (
            result.get("errors")
            or result.get("status") != "success"
        ):

            raise RuntimeError(
                json.dumps(
                    result,
                    ensure_ascii=False,
                )
            )

        return result

    def call(self, query):

        return self.post(
            "/db/data/cypher",
            {
                "statements": [
                    {
                        "query": query
                    }
                ]
            },
        )


# ============================================================
# UPLOAD
# ============================================================

def upload(
    client,
    nodes,
    edges,
):

    # Database exclusivo.
    # Não reutilizamos nem apagamos dados existentes.

    client.call(
        f"CREATE DATABASE {client.database}"
    )

    ids = {}

    # --------------------------------------------------------
    # Nós
    # --------------------------------------------------------

    for begin in range(
        0,
        len(nodes),
        40,
    ):

        result = client.post(
            "/db/data/node/bulk",
            {
                "rows":
                    nodes[begin:begin + 40]
            },
        )

        for row in result["resultados"]:

            ids[row["key"]] = row["id"]

    if len(ids) != len(nodes):

        raise RuntimeError(
            "Carga incompleta de nos"
        )

    # --------------------------------------------------------
    # Relacionamentos
    # --------------------------------------------------------

    for begin in range(
        0,
        len(edges),
        100,
    ):

        batch = [

            {
                "from":
                    ids[e["from_key"]],

                "to":
                    ids[e["to_key"]],

                "type":
                    e["type"],

                "properties":
                    e["properties"],
            }

            for e in edges[
                begin:begin + 100
            ]
        ]

        result = client.post(
            "/db/data/relationship/bulk",
            {
                "rows": batch
            },
        )

        if result["processados"] != len(batch):

            raise RuntimeError(
                "Carga incompleta de relacionamentos"
            )

    return ids


# ============================================================
# MEDIÇÃO
# ============================================================

def measured(
    client,
    query,
):

    start = time.perf_counter()

    result = client.call(query)

    elapsed = (
        time.perf_counter()
        - start
    ) * 1000

    return result, elapsed


# ============================================================
# SIMILARIDADE EXATA
# ============================================================

def dot_product(
    a,
    b,
):

    return sum(
        x * y
        for x, y in zip(a, b)
    )


def exact_search(
    vector,
    chunks,
    ids,
    k=3,
):

    ranked = sorted(

        chunks,

        key=lambda n: (

            -dot_product(
                vector,
                n["properties"]["embedding"],
            ),

            ids[n["key"]],
        ),
    )

    return ranked[:k]


# ============================================================
# DIAGNÓSTICO HNSW
# ============================================================

def print_vector_diagnostics(
    order,
    expected_doc,
    exact,
    hits,
    vector,
):

    exact_ids = [
        n["key"]
        for n in exact
    ]

    hnsw_ids = [
        h["node"]["properties"]["external_id"]
        for h in hits
    ]

    print()
    print("=" * 72)
    print(f"DIAGNOSTICO VETORIAL: {order}")
    print("=" * 72)

    print(
        f"Documento esperado : {expected_doc}"
    )

    print(
        f"Top-3 EXATO       : {exact_ids}"
    )

    print(
        f"Top-3 HNSW        : {hnsw_ids}"
    )

    print()
    print("Busca exata:")

    for position, node in enumerate(
        exact,
        1,
    ):

        score = dot_product(
            vector,
            node["properties"]["embedding"],
        )

        print(
            f"  {position:2}. "
            f"{node['key']:10} "
            f"score={score:.9f}"
        )

    print()
    print("Busca HNSW:")

    for position, hit in enumerate(
        hits,
        1,
    ):

        external_id = (
            hit["node"]
            ["properties"]
            ["external_id"]
        )

        print(
            f"  {position:2}. "
            f"{external_id:10} "
            f"score={hit.get('score')} "
            f"distance={hit.get('distance')}"
        )

    intersection = (
        set(exact_ids)
        &
        set(hnsw_ids)
    )

    recall = (
        len(intersection)
        /
        len(exact_ids)
        if exact_ids
        else 1.0
    )

    print()
    print(
        f"Recall@{len(exact_ids)}       : "
        f"{recall:.2%}"
    )

    print(
        "Intersecao        : "
        f"{sorted(intersection)}"
    )

    print("=" * 72)
    print()

    return {
        "exact_ids":
            exact_ids,

        "hnsw_ids":
            hnsw_ids,

        "recall":
            recall,

        "expected_found":
            expected_doc in hnsw_ids,
    }


# ============================================================
# AVALIAÇÃO
# ============================================================

def evaluate(
    client,
    model,
    chunks,
    ids,
    order,
):

    question = (
        f"Por que o pedido {order} "
        f"esta atrasado e qual fornecedor "
        f"esta relacionado?"
    )

    vector = model.encode(question)

    literal = json.dumps(
        vector,
        separators=(",", ":"),
    )

    # --------------------------------------------------------
    # Consultas
    # --------------------------------------------------------

    vector_query = (
        "CALL vector.search("
        f"'pedidos_texto',"
        f"{literal},"
        "3,"
        "128"
        ")"
    )

    graph_query = (
        "CALL graphRAG.retrieve("
        f"'pedidos_texto',"
        f"{literal},"
        "3,"
        "128,"
        "4,"
        "60"
        ")"
    )

    # --------------------------------------------------------
    # Warmup
    # --------------------------------------------------------

    _, cold_ms = measured(
        client,
        vector_query,
    )

    vector_times = []
    graph_times = []

    result = None
    context_result = None

    # --------------------------------------------------------
    # Repetições
    # --------------------------------------------------------

    for _ in range(3):

        result, ms = measured(
            client,
            vector_query,
        )

        vector_times.append(ms)

        context_result, ms = measured(
            client,
            graph_query,
        )

        graph_times.append(ms)

    # --------------------------------------------------------
    # Resultado HNSW
    # --------------------------------------------------------

    hits = result["resultados"]

    # --------------------------------------------------------
    # Resultado GraphRAG
    # --------------------------------------------------------

    context = (
        context_result["resultados"][0]
    )

    # --------------------------------------------------------
    # Busca exata brute-force
    # --------------------------------------------------------

    exact = exact_search(
        vector,
        chunks,
        ids,
        k=3,
    )

    exact_ids = {
        ids[n["key"]]
        for n in exact
    }

    hnsw_internal_ids = {
        h["node_id"]
        for h in hits
    }

    recall = (
        len(
            exact_ids
            &
            hnsw_internal_ids
        )
        / 3
    )

    # --------------------------------------------------------
    # Evidências esperadas
    # --------------------------------------------------------

    number = (
        int(order.split("-")[1])
        - 1000
    )

    expected_doc = (
        f"DOC-{number:03}"
    )

    expected = {

        order,

        f"LOT-{number:03}",

        f"EVT-{number:03}",

        f"CMP-{number % 20:02}",

        f"FOR-{number % 20:02}",

        f"CLI-{number % 30:02}",
    }

    evidence = {

        n["node"]
        ["properties"]
        ["external_id"]:
            n

        for n in context["nodes"]
    }

    # --------------------------------------------------------
    # DIAGNÓSTICO
    # --------------------------------------------------------

    diagnostic = (
        print_vector_diagnostics(
            order,
            expected_doc,
            exact,
            hits,
            vector,
        )
    )

    # --------------------------------------------------------
    # Verificação do HNSW
    # --------------------------------------------------------

    if not diagnostic["expected_found"]:

        raise AssertionError(

            f"HNSW recall failure para {order}: "
            f"esperado={expected_doc}; "
            f"exact={diagnostic['exact_ids']}; "
            f"hnsw={diagnostic['hnsw_ids']}; "
            f"recall@3={diagnostic['recall']:.2%}"
        )

    # --------------------------------------------------------
    # Verificação GraphRAG
    # --------------------------------------------------------

    missing = (
        expected
        -
        evidence.keys()
    )

    if missing:

        raise AssertionError(

            f"Evidencias GraphRAG incompletas "
            f"para {order}: "
            f"faltando={sorted(missing)}"
        )

    if context["truncated"]:

        raise AssertionError(

            f"Contexto GraphRAG truncado "
            f"para {order}"
        )

    # --------------------------------------------------------
    # Extrair causa e fornecedor
    # --------------------------------------------------------

    event = (
        evidence[
            f"EVT-{number:03}"
        ]
        ["node"]
        ["properties"]
    )

    supplier = (
        evidence[
            f"FOR-{number % 20:02}"
        ]
        ["node"]
        ["properties"]
    )

    # --------------------------------------------------------
    # Resposta determinística
    # --------------------------------------------------------

    answer = (

        f"{order}: a ocorrencia "
        f"{event['referencia']} registra: "
        f"{event['causa']}. "

        f"Impacto simulado: "
        f"{event['atraso_dias']} dias. "

        f"Acao registrada: "
        f"{event['acao']}. "

        f"Fornecedor associado ao componente: "
        f"{supplier['nome']}. "

        "A associacao nao atribui "
        "responsabilidade ao fornecedor."
    )

    # --------------------------------------------------------
    # Cobertura
    # --------------------------------------------------------

    vector_external_ids = {

        h["node"]
        ["properties"]
        ["external_id"]

        for h in hits
    }

    graph_coverage = (
        len(
            expected
            &
            evidence.keys()
        )
        /
        len(expected)
    )

    vector_coverage = (
        len(
            expected
            &
            vector_external_ids
        )
        /
        len(expected)
    )

    return {

        "order":
            order,

        "question":
            question,

        "answer_template":
            answer,

        "recall_at_3":
            recall,

        "expected_document":
            expected_doc,

        "exact_top3":
            diagnostic["exact_ids"],

        "hnsw_top3":
            diagnostic["hnsw_ids"],

        "expected_evidence":
            sorted(expected),

        "graph_evidence_coverage":
            graph_coverage,

        "vector_evidence_coverage":
            vector_coverage,

        "warmup_vector_ms":
            cold_ms,

        "vector_median_ms":
            statistics.median(
                vector_times
            ),

        "graph_median_ms":
            statistics.median(
                graph_times
            ),

        "vector_samples_ms":
            vector_times,

        "graph_samples_ms":
            graph_times,

        "vector_hits":
            hits,

        "graph_context":
            context,
    }


# ============================================================
# HTML
# ============================================================

def report_html(report):

    esc = lambda x: html.escape(str(x))

    sections = []

    for case in report["cases"]:

        hits = "".join(

            (
                "<li>"
                f"{esc(h['node']['properties']['titulo'])}"
                " — "
                f"{h['score']:.4f}"
                "</li>"
            )

            for h in case["vector_hits"]
        )

        evidence = "".join(

            (
                "<tr>"
                "<td>"
                f"{esc(n['node']['properties']['external_id'])}"
                "</td>"
                "<td>"
                f"{esc(n['node']['label'])}"
                "</td>"
                "<td>"
                f"{n['depth']}"
                "</td>"
                "</tr>"
            )

            for n
            in case["graph_context"]["nodes"]
        )

        sections.append(

            f"""
            <section>

            <h2>
            {esc(case["question"])}
            </h2>

            <div class="columns">

            <article>

            <h3>
            Somente busca vetorial
            </h3>

            <ol>
            {hits}
            </ol>

            <p>
            Top-3 exato:
            {esc(case["exact_top3"])}
            </p>

            <p>
            Top-3 HNSW:
            {esc(case["hnsw_top3"])}
            </p>

            </article>

            <article>

            <h3>
            Busca + grafo
            </h3>

            <p>
            {esc(case["answer_template"])}
            </p>

            <p>
            Resposta por template;
            sem LLM.
            </p>

            </article>

            </div>

            <p>
            Recall@3:
            {case["recall_at_3"]:.0%}

            · HTTP vetorial:
            {case["vector_median_ms"]:.1f} ms

            · HTTP GraphRAG:
            {case["graph_median_ms"]:.1f} ms
            </p>

            <details>

            <summary>
            Nos recuperados e profundidade
            </summary>

            <table>

            <tr>
            <th>ID</th>
            <th>Tipo</th>
            <th>Saltos</th>
            </tr>

            {evidence}

            </table>

            </details>

            </section>
            """
        )

    return (

        """
        <!doctype html>

        <html lang="pt-BR">

        <meta charset="utf-8">

        <meta
            name="viewport"
            content="width=device-width"
        >

        <title>
        NexusDB — Pedidos e GraphRAG
        </title>

        <style>

        body {
            font: 16px system-ui;
            background: #f3f6fa;
            color: #15253b;
            max-width: 1100px;
            margin: 40px auto;
            padding: 0 20px;
        }

        h1 {
            font-size: 36px;
        }

        section {
            background: white;
            padding: 24px;
            margin: 24px 0;
            border-radius: 12px;
        }

        .columns {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 28px;
        }

        td,
        th {
            text-align: left;
            padding: 6px 18px;
            border-bottom: 1px solid #ddd;
        }

        p {
            line-height: 1.6;
        }

        @media(max-width:700px) {

            .columns {
                grid-template-columns: 1fr;
            }

        }

        </style>

        <h1>
        Por que meu pedido atrasou?
        </h1>
        """

        +

        f"""
        <p>
        Database:
        {esc(report["database"])}.

        {report["nodes"]} nos,
        {report["edges"]} relacoes,
        {report["chunks"]} textos e
        {report["dimensions"]} dimensoes TF-IDF.
        </p>

        <p>
        Dados ficticios;
        vetores lexicais locais.
        Comparacao entre busca exata,
        HNSW e GraphRAG.
        </p>

        <p>
        Chunk → Pedido → Lote → Ocorrencia;
        Lote → Componente → Fornecedor.
        </p>

        <p>
        Inspirado no
        <a href="{SOURCE}">
        cenario de atendimento descrito pela Memgraph
        </a>.
        </p>
        """

        +

        "".join(sections)

        +

        "</html>"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--url",
        default=os.getenv(
            "NEXUSDB_DEMO_URL",
            "http://127.0.0.1:7474",
        ),
    )

    parser.add_argument(
        "--user",
        default=os.getenv(
            "NEXUSDB_TEST_USER",
            "administrador2",
        ),
    )

    parser.add_argument(

        "--database",

        default=(

            "GRAPHRAG_PEDIDOS_"

            + datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            + "_"

            + uuid.uuid4().hex[:6]
        ),
    )

    parser.add_argument(
        "--order",
        default="PED-1042",
        help="PED-1000 ate PED-1119",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=(
            Path(__file__).parent
            /
            "output"
        ),
    )

    parser.add_argument(
        "--generate-only",
        action="store_true",
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Validações
    # --------------------------------------------------------

    if not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_]{0,100}",
        args.database,
    ):

        parser.error(
            "Nome de database invalido"
        )

    if (
        not re.fullmatch(
            r"PED-\d{4}",
            args.order,
        )
        or
        not (
            1000
            <= int(args.order[4:])
            <= 1119
        )
    ):

        parser.error(
            "Pedido fora do intervalo "
            "PED-1000..PED-1119"
        )

    # --------------------------------------------------------
    # Dataset
    # --------------------------------------------------------

    nodes, edges = dataset()

    chunks = [
        n
        for n in nodes
        if n["label"] == "Chunk"
    ]

    # --------------------------------------------------------
    # TF-IDF
    # --------------------------------------------------------

    model = Tfidf(

        [
            n["properties"]["texto"]
            for n in chunks
        ]
    )

    for n in chunks:

        n["properties"]["embedding"] = (
            model.encode(
                n["properties"]["texto"]
            )
        )

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    args.output.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        args.output
        /
        "dataset.json"
    ).write_text(

        json.dumps(
            {
                "nodes": nodes,
                "edges": edges,
            },
            ensure_ascii=False,
        ),

        encoding="utf-8",
    )

    print(
        f"Gerados {len(nodes)} nos, "
        f"{len(edges)} relacoes, "
        f"{len(chunks)} textos; "
        f"TF-IDF "
        f"{len(model.vocabulary)} dimensoes."
    )

    if args.generate_only:
        return

    # --------------------------------------------------------
    # Autenticação
    # --------------------------------------------------------

    password = (
        os.getenv(
            "NEXUSDB_TEST_PASSWORD"
        )
        or
        getpass.getpass(
            "Senha do NexusDB "
            "(nao sera gravada): "
        )
    )

    client = Client(
        args.url,
        args.user,
        password,
        args.database,
    )

    # --------------------------------------------------------
    # Criar database
    # --------------------------------------------------------

    print(
        f"Criando database exclusivo "
        f"{args.database}..."
    )

    ids = upload(
        client,
        nodes,
        edges,
    )

    # --------------------------------------------------------
    # Criar HNSW
    # --------------------------------------------------------

    print(
        "Criando indice vetorial "
        "pedidos_texto..."
    )

    client.call(

        "CALL vector.createIndex("
        "'pedidos_texto',"
        "'Chunk',"
        "'embedding',"
        f"{len(model.vocabulary)},"
        "'cosine'"
        ")"
    )

    # --------------------------------------------------------
    # Mostrar índices
    # --------------------------------------------------------

    indexes = client.call(
        "CALL vector.listIndexes()"
    )

    print()
    print("Indices vetoriais:")

    print(
        json.dumps(
            indexes,
            ensure_ascii=False,
            indent=2,
        )
    )

    # --------------------------------------------------------
    # Casos
    # --------------------------------------------------------

    cases = []

    test_orders = dict.fromkeys(
        [
            args.order,
            "PED-1000",
            "PED-1001",
            "PED-1003",
            "PED-1057",
            "PED-1119",
        ]
    )

    for order in test_orders:

        print()
        print(
            f"Testando {order}..."
        )

        case = evaluate(
            client,
            model,
            chunks,
            ids,
            order,
        )

        cases.append(case)

        print(
            f"[OK] {order}: "
            f"recall@3="
            f"{case['recall_at_3']:.0%}; "
            f"evidencias="
            f"{case['graph_evidence_coverage']:.0%}"
        )

        print(
            case["answer_template"]
        )

    # --------------------------------------------------------
    # Relatório
    # --------------------------------------------------------

    report = {

        "database":
            args.database,

        "nodes":
            len(nodes),

        "edges":
            len(edges),

        "chunks":
            len(chunks),

        "dimensions":
            len(model.vocabulary),

        "embedding":
            "TF-IDF lexical, nao neural",

        "cases":
            cases,
    }

    report_json = (
        args.output
        /
        "report.json"
    )

    report_html_path = (
        args.output
        /
        "report.html"
    )

    model_json = (
        args.output
        /
        "model.json"
    )

    report_json.write_text(

        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),

        encoding="utf-8",
    )

    report_html_path.write_text(
        report_html(report),
        encoding="utf-8",
    )

    model_json.write_text(

        json.dumps(
            {
                "vocabulary":
                    model.vocabulary,

                "idf":
                    model.idf,
            },
            ensure_ascii=False,
            indent=2,
        ),

        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("TESTES CONCLUIDOS")
    print("=" * 72)

    print(
        f"Relatorio JSON: "
        f"{report_json.resolve()}"
    )

    print(
        f"Relatorio HTML: "
        f"{report_html_path.resolve()}"
    )

    print(
        f"Database preservado: "
        f"{args.database}."
    )

    print(
        "Nenhum dado preexistente "
        "foi removido."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except (
        RuntimeError,
        ValueError,
        AssertionError,
        OSError,
    ) as error:

        print()
        print("=" * 72)
        print("ERRO")
        print("=" * 72)

        print(error)

        raise SystemExit(1)