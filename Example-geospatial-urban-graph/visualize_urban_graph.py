#!/usr/bin/env python3
"""Visualize a NexusDB urban POI graph as static PNG images.

Reads POI, Bairro, NEAR and LOCATED_IN data from NexusDB's Cypher-like HTTP API
and produces:
- urban_map_and_graph.png
- bairro_summary.png
- poi_category_map.png
- top_hubs.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import requests


class NexusClient:
    def __init__(self, base_url: str, user: str, password: str, database: str):
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.database = database

    def cypher(self, query: str) -> dict:
        url = f"{self.base_url}/db/data/cypher"
        headers = {
            "Content-Type": "application/json",
            "X-User": self.user,
            "X-Pass": self.password,
            "X-Database": self.database,
        }
        payload = {"statements": [{"query": query}]}

        resp = requests.post(url, headers=headers, json=payload, timeout=180)
        if not resp.ok:
            raise RuntimeError(
                f"HTTP {resp.status_code} from {url}: {resp.text[:1000]}"
            )

        data = resp.json()
        if data.get("errors"):
            raise RuntimeError(
                "NexusDB returned query errors: "
                + json.dumps(data["errors"], ensure_ascii=False)
            )
        return data


def fetch_dataframe(client: NexusClient, query: str) -> pd.DataFrame:
    result = client.cypher(query)
    rows = result.get("resultados", [])
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def normalize_columns(
    frame: pd.DataFrame,
    mapping: dict[str, list[str]],
    label: str,
) -> pd.DataFrame:
    """Normalize NexusDB projection column names across parser variants.

    Some NexusDB builds preserve the requested projection text literally
    (for example 'p.external_id AS poi_id') instead of returning only the
    alias. This helper accepts both forms and renames them to stable names
    used by the visualizer.
    """
    if frame.empty:
        return frame

    renamed = {}
    columns = [str(col) for col in frame.columns]

    for target, candidates in mapping.items():
        if target in frame.columns:
            continue

        match = None
        for candidate in candidates:
            if candidate in frame.columns:
                match = candidate
                break

        if match is None:
            # Fallback for literal projections such as:
            # "p.external_id AS poi_id"
            target_cf = target.casefold()
            for col in columns:
                col_cf = col.casefold().strip()
                if (
                    col_cf.endswith(f" as {target_cf}")
                    or col_cf == target_cf
                    or col_cf.endswith("." + target_cf)
                ):
                    match = col
                    break

        if match is not None:
            renamed[match] = target

    if renamed:
        frame = frame.rename(columns=renamed)

    missing = [target for target in mapping if target not in frame.columns]
    if missing:
        raise RuntimeError(
            f"{label}: expected columns {missing}, but NexusDB returned "
            f"{list(frame.columns)}"
        )

    return frame


def _entity_properties(value) -> dict:
    """Return a flat property dict from a NexusDB node/relationship value."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        return {"value": value}

    for key in ("properties", "props", "property"):
        props = value.get(key)
        if isinstance(props, dict):
            out = dict(props)
            if "id" in value and "_id" not in out:
                out["_id"] = value["id"]
            if "type" in value and "_type" not in out:
                out["_type"] = value["type"]
            if "labels" in value and "_labels" not in out:
                out["_labels"] = value["labels"]
            return out

    # Some NexusDB projections already return the property map directly.
    return dict(value)


def _node_frame(rows: list[dict], key: str, id_name: str, name_name: str | None = None) -> pd.DataFrame:
    out = []
    for row in rows:
        props = _entity_properties(row.get(key))
        if not props:
            continue
        record = dict(props)
        if id_name not in record:
            # Prefer explicit external_id from imported data.
            if "external_id" in record:
                record[id_name] = record["external_id"]
            elif "_id" in record:
                record[id_name] = record["_id"]
        if name_name and name_name not in record and "name" in record:
            record[name_name] = record["name"]
        out.append(record)
    return pd.DataFrame(out)


def _near_frame(rows: list[dict]) -> pd.DataFrame:
    out = []
    for row in rows:
        a = _entity_properties(row.get("a"))
        b = _entity_properties(row.get("b"))
        r = _entity_properties(row.get("r"))
        source_id = a.get("external_id", a.get("_id"))
        target_id = b.get("external_id", b.get("_id"))
        if source_id is None or target_id is None:
            continue
        out.append(
            {
                "source_id": str(source_id),
                "target_id": str(target_id),
                "distance_m": r.get("distance_m"),
            }
        )
    return pd.DataFrame(out)


def _located_frame(rows: list[dict]) -> pd.DataFrame:
    out = []
    for row in rows:
        p = _entity_properties(row.get("p"))
        b = _entity_properties(row.get("b"))
        poi_id = p.get("external_id", p.get("_id"))
        bairro_id = b.get("external_id", b.get("_id"))
        if poi_id is None or bairro_id is None:
            continue
        out.append(
            {
                "poi_id": str(poi_id),
                "bairro_id": str(bairro_id),
                "bairro_name": b.get("name", ""),
            }
        )
    return pd.DataFrame(out)


def load_graph_data(client: NexusClient):
    """Read full entities and unpack their property maps.

    NexusDB currently returns entity variables such as `p`, `a`, `r`, and
    `b` more reliably than dotted property projections with SQL-like aliases.
    Therefore the visualizer deliberately uses RETURN p / RETURN a,r,b and
    normalizes the entity objects in Python.
    """
    poi_result = client.cypher(
        """
        MATCH (p:POI)
        RETURN p
        """
    )
    bairro_result = client.cypher(
        """
        MATCH (b:Bairro)
        RETURN b
        """
    )
    near_result = client.cypher(
        """
        MATCH (a:POI)-[r:NEAR]->(b:POI)
        RETURN a, r, b
        """
    )
    located_result = client.cypher(
        """
        MATCH (p:POI)-[r:LOCATED_IN]->(b:Bairro)
        RETURN p, r, b
        """
    )

    poi_rows = poi_result.get("resultados", [])
    bairro_rows = bairro_result.get("resultados", [])
    near_rows = near_result.get("resultados", [])
    located_rows = located_result.get("resultados", [])

    pois = _node_frame(poi_rows, "p", "poi_id")
    bairros = _node_frame(bairro_rows, "b", "bairro_id", "bairro_name")
    near = _near_frame(near_rows)
    located = _located_frame(located_rows)

    if pois.empty:
        sample = poi_rows[:2]
        raise RuntimeError(
            "No POI nodes could be decoded from NexusDB entity rows. "
            f"Sample response: {sample}"
        )

    required_poi = {"poi_id", "name", "category", "latitude", "longitude"}
    missing = sorted(required_poi.difference(pois.columns))
    if missing:
        raise RuntimeError(
            f"POI entities are missing expected properties {missing}; "
            f"available columns: {list(pois.columns)}"
        )

    for col in ("latitude", "longitude"):
        pois[col] = pd.to_numeric(pois[col], errors="coerce")

    if not near.empty and "distance_m" in near.columns:
        near["distance_m"] = pd.to_numeric(near["distance_m"], errors="coerce")

    # Ensure expected optional columns exist so plotting/merging stays simple.
    for col in ("address", "bairro"):
        if col not in pois.columns:
            pois[col] = None

    for col in ("bairro_id", "bairro_name"):
        if col not in bairros.columns:
            bairros[col] = None

    return pois, bairros, near, located


def build_network(pois: pd.DataFrame, near: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()

    for _, row in pois.iterrows():
        graph.add_node(
            row["poi_id"],
            name=row.get("name"),
            category=row.get("category"),
            bairro=row.get("bairro"),
            latitude=row.get("latitude"),
            longitude=row.get("longitude"),
        )

    if not near.empty:
        for _, row in near.iterrows():
            src = row["source_id"]
            dst = row["target_id"]
            if src == dst:
                continue
            graph.add_edge(
                src,
                dst,
                distance_m=row.get("distance_m"),
            )

    return graph


def category_color_map(categories):
    cmap = plt.get_cmap("tab10")
    names = sorted(str(c) for c in categories if pd.notna(c))
    return {name: cmap(i % 10) for i, name in enumerate(names)}


def plot_category_map(pois: pd.DataFrame, output_path: Path) -> None:
    valid = pois.dropna(subset=["latitude", "longitude"]).copy()
    if valid.empty:
        raise RuntimeError("POIs do not contain valid latitude/longitude values.")

    valid["category_plot"] = valid["category"].fillna("unknown").astype(str)
    colors = category_color_map(valid["category_plot"].unique())

    fig, ax = plt.subplots(figsize=(12, 10))
    for category, group in valid.groupby("category_plot"):
        ax.scatter(
            group["longitude"],
            group["latitude"],
            s=34,
            alpha=0.85,
            label=category,
            color=colors[category],
        )

    ax.set_title("POIs de Niterói por categoria")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.legend(loc="best", fontsize=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_map_and_graph(
    pois: pd.DataFrame,
    near: pd.DataFrame,
    graph: nx.Graph,
    output_path: Path,
    title: str,
) -> None:
    fig, (ax_map, ax_graph) = plt.subplots(1, 2, figsize=(20, 10))

    poi_lookup = pois.set_index("poi_id")
    categories = pois["category"].fillna("unknown").astype(str)
    colors = category_color_map(categories.unique())

    if not near.empty:
        for _, row in near.iterrows():
            src, dst = row["source_id"], row["target_id"]
            if src not in poi_lookup.index or dst not in poi_lookup.index:
                continue
            a = poi_lookup.loc[src]
            b = poi_lookup.loc[dst]
            vals = [a["longitude"], a["latitude"], b["longitude"], b["latitude"]]
            if any(pd.isna(v) for v in vals):
                continue
            ax_map.plot(
                [a["longitude"], b["longitude"]],
                [a["latitude"], b["latitude"]],
                linewidth=0.35,
                alpha=0.20,
            )

    temp = pois.copy()
    temp["category_plot"] = categories
    for category, group in temp.groupby("category_plot"):
        ax_map.scatter(
            group["longitude"],
            group["latitude"],
            s=28,
            alpha=0.90,
            label=category,
            color=colors[category],
        )

    degree = dict(graph.degree())
    top_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:12]
    for node_id, _ in top_nodes:
        if node_id not in poi_lookup.index:
            continue
        row = poi_lookup.loc[node_id]
        if pd.isna(row["longitude"]) or pd.isna(row["latitude"]):
            continue
        ax_map.text(
            row["longitude"],
            row["latitude"],
            str(row.get("name", node_id))[:36],
            fontsize=6,
        )

    ax_map.set_title("Mapa geográfico + relações NEAR")
    ax_map.set_xlabel("Longitude")
    ax_map.set_ylabel("Latitude")
    ax_map.legend(loc="best", fontsize=7)

    if graph.number_of_nodes() > 0:
        pos = nx.spring_layout(graph, seed=42, k=0.30, iterations=80)
        node_colors = []
        node_sizes = []
        for node in graph.nodes:
            category = str(graph.nodes[node].get("category") or "unknown")
            node_colors.append(colors.get(category, plt.get_cmap("tab10")(0)))
            node_sizes.append(28 + graph.degree(node) * 5)

        nx.draw_networkx_edges(
            graph,
            pos,
            ax=ax_graph,
            width=0.45,
            alpha=0.20,
        )
        nx.draw_networkx_nodes(
            graph,
            pos,
            ax=ax_graph,
            node_color=node_colors,
            node_size=node_sizes,
            alpha=0.88,
        )
        labels = {
            node: str(graph.nodes[node].get("name") or node)[:28]
            for node, _ in top_nodes
        }
        nx.draw_networkx_labels(
            graph,
            pos,
            labels=labels,
            font_size=6,
            ax=ax_graph,
        )

    ax_graph.set_title("Grafo estrutural (spring layout)")
    ax_graph.axis("off")

    fig.suptitle(title, fontsize=15)
    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_bairro_summary(
    pois: pd.DataFrame,
    located: pd.DataFrame,
    output_path: Path,
) -> None:
    if located.empty:
        print("WARNING: no LOCATED_IN relationships; skipping bairro_summary.png")
        return

    merged = located.merge(
        pois[["poi_id", "category"]],
        on="poi_id",
        how="left",
    )

    summary = (
        merged.groupby("bairro_name")
        .agg(
            poi_count=("poi_id", "nunique"),
            category_count=("category", "nunique"),
        )
        .sort_values(["poi_count", "category_count"], ascending=[False, False])
        .head(20)
        .reset_index()
    )

    if summary.empty:
        return

    fig, ax = plt.subplots(figsize=(12, 8))
    y = list(range(len(summary)))
    ax.barh(y, summary["poi_count"])
    ax.set_yticks(y)
    ax.set_yticklabels(summary["bairro_name"])
    ax.invert_yaxis()
    ax.set_xlabel("Quantidade de POIs")
    ax.set_title("Top 20 bairros por quantidade de POIs")

    for i, row in summary.iterrows():
        ax.text(
            row["poi_count"] + 0.25,
            i,
            f"{int(row['category_count'])} categorias",
            va="center",
            fontsize=8,
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def export_top_hubs(
    graph: nx.Graph,
    output_path: Path,
) -> None:
    degree = dict(graph.degree())
    pagerank = nx.pagerank(graph) if graph.number_of_nodes() else {}

    rows = []
    for node in graph.nodes:
        attrs = graph.nodes[node]
        rows.append(
            {
                "poi_id": node,
                "name": attrs.get("name"),
                "category": attrs.get("category"),
                "bairro": attrs.get("bairro"),
                "degree": degree.get(node, 0),
                "pagerank": pagerank.get(node, 0.0),
            }
        )

    pd.DataFrame(rows).sort_values(
        ["degree", "pagerank"],
        ascending=[False, False],
    ).to_csv(output_path, index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:7474")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output/visual"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("Conectando ao NexusDB...")
    client = NexusClient(args.url, args.user, args.password, args.database)

    print("Lendo dados do banco...")
    pois, bairros, near, located = load_graph_data(client)

    print(f"POIs..............: {len(pois)}")
    print(f"Bairros...........: {len(bairros)}")
    print(f"Relações NEAR.....: {len(near)}")
    print(f"Relações LOCATED..: {len(located)}")

    print("Construindo grafo...")
    graph = build_network(pois, near)

    print("Gerando imagens...")
    plot_map_and_graph(
        pois,
        near,
        graph,
        args.output_dir / "urban_map_and_graph.png",
        f"NexusDB Urban Graph - {args.database}",
    )
    plot_bairro_summary(
        pois,
        located,
        args.output_dir / "bairro_summary.png",
    )
    plot_category_map(
        pois,
        args.output_dir / "poi_category_map.png",
    )
    export_top_hubs(
        graph,
        args.output_dir / "top_hubs.csv",
    )

    print()
    print("Arquivos gerados:")
    for name in (
        "urban_map_and_graph.png",
        "bairro_summary.png",
        "poi_category_map.png",
        "top_hubs.csv",
    ):
        print(f"  {args.output_dir / name}")


if __name__ == "__main__":
    main()
