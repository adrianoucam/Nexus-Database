"""
Benchmark NexusDB Vector/HNSW
=============================

- 10.000 vetores
- dimensão configurável (default 128)
- vetores determinísticos
- ground truth por brute-force
- HNSW NexusDB
- Recall@10
- latência p50/p95
- vários ef_search
- relatório JSON

Somente Python stdlib.
"""

import argparse
import getpass
import json
import math
import os
import random
import statistics
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path


# ============================================================
# CONFIGURAÇÃO
# ============================================================

DEFAULT_VECTORS = 10_000
DEFAULT_DIMENSIONS = 128
DEFAULT_K = 10
DEFAULT_QUERIES = 50

EF_VALUES = [16, 32, 64, 128, 256, 512]


# ============================================================
# CLIENTE NEXUSDB
# ============================================================

class Client:

    def __init__(self, url, user, password, database):
        self.url = url.rstrip("/")
        self.user = user
        self.password = password
        self.database = database

    def post(self, route, payload):

        request = urllib.request.Request(
            self.url + route,
            json.dumps(payload).encode("utf-8"),
            {
                "Content-Type": "application/json",
                "X-User": self.user,
                "X-Pass": self.password,
                "X-Database": self.database,
            },
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=180,
            ) as response:

                result = json.load(response)

        except urllib.error.HTTPError as error:

            body = error.read().decode(
                errors="replace"
            )

            raise RuntimeError(
                f"HTTP {error.code}: {body}"
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
                    {"query": query}
                ]
            },
        )


# ============================================================
# VETORES
# ============================================================

def normalize(v):

    norm = math.sqrt(
        sum(x * x for x in v)
    )

    return [
        x / norm
        for x in v
    ]


def generate_vectors(
    count,
    dimensions,
    seed=42,
):

    rng = random.Random(seed)

    vectors = []

    print(
        f"Gerando {count:,} vetores "
        f"de {dimensions} dimensoes..."
    )

    for i in range(count):

        # Distribuição aleatória determinística.
        v = [
            rng.uniform(-1.0, 1.0)
            for _ in range(dimensions)
        ]

        vectors.append(
            normalize(v)
        )

        if (
            (i + 1) % 1000 == 0
            or i + 1 == count
        ):
            print(
                f"\r  {i+1:,}/{count:,}",
                end="",
                flush=True,
            )

    print()

    return vectors


# ============================================================
# GROUND TRUTH
# ============================================================

def dot(a, b):

    return sum(
        x * y
        for x, y in zip(a, b)
    )


def exact_search(
    vectors,
    query,
    k,
):

    scores = []

    for i, vector in enumerate(vectors):

        score = dot(
            query,
            vector,
        )

        scores.append(
            (score, i)
        )

    scores.sort(
        key=lambda x: (
            -x[0],
            x[1],
        )
    )

    return scores[:k]


# ============================================================
# RECALL
# ============================================================

def recall_at_k(
    exact_ids,
    hnsw_ids,
):

    return (
        len(
            set(exact_ids)
            &
            set(hnsw_ids)
        )
        /
        len(exact_ids)
    )


# ============================================================
# PERCENTIL
# ============================================================

def percentile(
    values,
    p,
):

    if not values:
        return 0.0

    values = sorted(values)

    index = (
        len(values) - 1
    ) * p

    lower = math.floor(index)
    upper = math.ceil(index)

    if lower == upper:
        return values[lower]

    return (
        values[lower]
        +
        (
            values[upper]
            -
            values[lower]
        )
        *
        (index - lower)
    )


# ============================================================
# UPLOAD
# ============================================================

def upload_vectors(
    client,
    vectors,
    batch_size=100,
):

    print()
    print("Importando vetores no NexusDB...")

    node_ids = {}

    total = len(vectors)

    start_total = time.perf_counter()

    for begin in range(
        0,
        total,
        batch_size,
    ):

        end = min(
            begin + batch_size,
            total,
        )

        rows = []

        for i in range(
            begin,
            end,
        ):

            rows.append(
                {
                    "key":
                        f"VEC-{i:05}",

                    "label":
                        "VectorBenchmark",

                    "properties":
                        {
                            "external_id":
                                f"VEC-{i:05}",

                            "sequence":
                                i,

                            "embedding":
                                vectors[i],
                        },
                }
            )

        result = client.post(
            "/db/data/node/bulk",
            {
                "rows": rows
            },
        )

        for row in result["resultados"]:

            node_ids[
                int(
                    row["key"].split("-")[1]
                )
            ] = row["id"]

        print(
            f"\r  {end:,}/{total:,}",
            end="",
            flush=True,
        )

    print()

    elapsed = (
        time.perf_counter()
        -
        start_total
    )

    if len(node_ids) != total:

        raise RuntimeError(
            f"Upload incompleto: "
            f"{len(node_ids)}/{total}"
        )

    print(
        f"Upload concluido em "
        f"{elapsed:.2f} s"
    )

    print(
        f"Taxa: "
        f"{total / elapsed:.1f} vetores/s"
    )

    return node_ids, elapsed


# ============================================================
# CONSULTA NEXUSDB
# ============================================================

def nexus_search(
    client,
    query,
    k,
    ef,
):

    literal = json.dumps(
        query,
        separators=(",", ":"),
    )

    cypher = (
        "CALL vector.search("
        "'benchmark_10k',"
        f"{literal},"
        f"{k},"
        f"{ef}"
        ")"
    )

    start = time.perf_counter()

    result = client.call(
        cypher
    )

    elapsed_ms = (
        time.perf_counter()
        -
        start
    ) * 1000

    return (
        result["resultados"],
        elapsed_ms,
    )


# ============================================================
# BENCHMARK
# ============================================================

def benchmark(
    client,
    vectors,
    node_ids,
    query_indices,
    k,
    ef_values,
):

    # NexusDB ID -> índice original
    reverse_ids = {
        node_id: index
        for index, node_id
        in node_ids.items()
    }

    results = []

    print()
    print("=" * 72)
    print("BENCHMARK HNSW")
    print("=" * 72)

    for ef in ef_values:

        print()
        print(
            f"ef_search = {ef}"
        )

        recalls = []
        latencies = []
        exact_times = []

        failures = 0

        for position, query_index in enumerate(
            query_indices,
            1,
        ):

            query = vectors[
                query_index
            ]

            # --------------------------------------------
            # Ground truth
            # --------------------------------------------

            start = time.perf_counter()

            exact = exact_search(
                vectors,
                query,
                k,
            )

            exact_ms = (
                time.perf_counter()
                -
                start
            ) * 1000

            exact_times.append(
                exact_ms
            )

            exact_ids = [
                index
                for _, index
                in exact
            ]

            # --------------------------------------------
            # NexusDB HNSW
            # --------------------------------------------

            hits, latency = (
                nexus_search(
                    client,
                    query,
                    k,
                    ef,
                )
            )

            latencies.append(
                latency
            )

            hnsw_ids = []

            for hit in hits:

                internal_id = (
                    hit["node_id"]
                )

                if internal_id in reverse_ids:

                    hnsw_ids.append(
                        reverse_ids[
                            internal_id
                        ]
                    )

            recall = recall_at_k(
                exact_ids,
                hnsw_ids,
            )

            recalls.append(
                recall
            )

            if recall < 1.0:
                failures += 1

            print(
                f"\r"
                f"  query "
                f"{position:02}/"
                f"{len(query_indices)} "
                f"recall={recall:6.1%} "
                f"lat={latency:8.2f} ms",
                end="",
                flush=True,
            )

        print()

        summary = {

            "ef_search":
                ef,

            "queries":
                len(query_indices),

            "recall_mean":
                statistics.mean(recalls),

            "recall_min":
                min(recalls),

            "recall_100_percent_queries":
                sum(
                    1
                    for r in recalls
                    if r == 1.0
                ),

            "queries_below_100_percent":
                failures,

            "latency_mean_ms":
                statistics.mean(latencies),

            "latency_p50_ms":
                statistics.median(latencies),

            "latency_p95_ms":
                percentile(
                    latencies,
                    0.95,
                ),

            "latency_max_ms":
                max(latencies),

            "exact_mean_ms":
                statistics.mean(
                    exact_times
                ),

            "exact_p50_ms":
                statistics.median(
                    exact_times
                ),
        }

        results.append(
            summary
        )

        print(
            f"  Recall medio : "
            f"{summary['recall_mean']:.2%}"
        )

        print(
            f"  Recall minimo: "
            f"{summary['recall_min']:.2%}"
        )

        print(
            f"  HNSW p50     : "
            f"{summary['latency_p50_ms']:.2f} ms"
        )

        print(
            f"  HNSW p95     : "
            f"{summary['latency_p95_ms']:.2f} ms"
        )

        print(
            f"  Exact p50    : "
            f"{summary['exact_p50_ms']:.2f} ms"
        )

    return results


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
        "--vectors",
        type=int,
        default=DEFAULT_VECTORS,
    )

    parser.add_argument(
        "--dimensions",
        type=int,
        default=DEFAULT_DIMENSIONS,
    )

    parser.add_argument(
        "--queries",
        type=int,
        default=DEFAULT_QUERIES,
    )

    parser.add_argument(
        "--k",
        type=int,
        default=DEFAULT_K,
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

    args = parser.parse_args()

    database = (
        "VECTOR_BENCH_"
        +
        datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        +
        "_"
        +
        uuid.uuid4().hex[:6]
    )

    print("=" * 72)
    print("NexusDB Vector/HNSW Benchmark")
    print("=" * 72)

    print(
        f"Vetores    : {args.vectors:,}"
    )

    print(
        f"Dimensoes  : {args.dimensions}"
    )

    print(
        f"Queries    : {args.queries}"
    )

    print(
        f"K          : {args.k}"
    )

    print(
        f"Database   : {database}"
    )

    # --------------------------------------------------------
    # Vetores
    # --------------------------------------------------------

    vectors = generate_vectors(
        args.vectors,
        args.dimensions,
        seed=42,
    )

    # --------------------------------------------------------
    # Queries
    #
    # Usamos vetores existentes.
    # Assim o próprio vetor deve estar no ground truth.
    # --------------------------------------------------------

    rng = random.Random(2026)

    query_indices = rng.sample(
        range(args.vectors),
        min(
            args.queries,
            args.vectors,
        ),
    )

    # --------------------------------------------------------
    # Login
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
        database,
    )

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    print()
    print(
        f"Criando database "
        f"{database}..."
    )

    client.call(
        f"CREATE DATABASE {database}"
    )

    # --------------------------------------------------------
    # Upload
    # --------------------------------------------------------

    node_ids, upload_seconds = (
        upload_vectors(
            client,
            vectors,
            batch_size=100,
        )
    )

    # --------------------------------------------------------
    # HNSW
    # --------------------------------------------------------

    print()
    print(
        "Criando indice HNSW..."
    )

    start = time.perf_counter()

    client.call(
        "CALL vector.createIndex("
        "'benchmark_10k',"
        "'VectorBenchmark',"
        "'embedding',"
        f"{args.dimensions},"
        "'cosine'"
        ")"
    )

    build_seconds = (
        time.perf_counter()
        -
        start
    )

    print(
        f"Indice criado em "
        f"{build_seconds:.2f} s"
    )

    # --------------------------------------------------------
    # Warmup
    # --------------------------------------------------------

    print()
    print("Warmup...")

    nexus_search(
        client,
        vectors[
            query_indices[0]
        ],
        args.k,
        128,
    )

    # --------------------------------------------------------
    # Benchmark
    # --------------------------------------------------------

    results = benchmark(
        client,
        vectors,
        node_ids,
        query_indices,
        args.k,
        EF_VALUES,
    )

    # --------------------------------------------------------
    # Relatório
    # --------------------------------------------------------

    report = {

        "database":
            database,

        "vectors":
            args.vectors,

        "dimensions":
            args.dimensions,

        "queries":
            len(query_indices),

        "k":
            args.k,

        "metric":
            "cosine",

        "upload_seconds":
            upload_seconds,

        "index_build_seconds":
            build_seconds,

        "ef_results":
            results,
    }

    args.output.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = (
        args.output
        /
        "benchmark_10k.json"
    )

    output.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Resumo
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("RESULTADO FINAL")
    print("=" * 72)

    print()
    print(
        f"{'EF':>6} "
        f"{'Recall':>10} "
        f"{'Min':>10} "
        f"{'P50 ms':>12} "
        f"{'P95 ms':>12}"
    )

    print("-" * 56)

    for row in results:

        print(
            f"{row['ef_search']:6} "
            f"{row['recall_mean']:10.2%} "
            f"{row['recall_min']:10.2%} "
            f"{row['latency_p50_ms']:12.2f} "
            f"{row['latency_p95_ms']:12.2f}"
        )

    print()
    print(
        f"Build HNSW : "
        f"{build_seconds:.2f} s"
    )

    print(
        f"Relatorio  : "
        f"{output.resolve()}"
    )

    print(
        f"Database preservado: "
        f"{database}"
    )


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