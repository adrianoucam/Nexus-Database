#!/usr/bin/env python3
"""Interactive didactic urban graph map for NexusDB.

Run:
    streamlit run interactive_urban_map.py

The app reads POI/Bairro/NEAR/LOCATED_IN entities from NexusDB, supports
category/bairro/name filters, POI inspection, direct geographic distance and
weighted shortest paths over the NEAR proximity graph.

Important: NEAR is a fixed-radius proximity relation, not a street-routing
network. Its path distance must not be interpreted as walking/driving distance.
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict

import folium
from folium.plugins import MarkerCluster
import networkx as nx
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium


DEFAULT_URL = os.getenv("NEXUSDB_URL", "http://127.0.0.1:7474")
DEFAULT_USER = os.getenv("NEXUSDB_USER", "admin")
DEFAULT_PASSWORD = os.getenv("NEXUSDB_PASSWORD", "")
DEFAULT_DATABASE = os.getenv("NEXUSDB_DATABASE", "")


class NexusClient:
    def __init__(self, base_url: str, user: str, password: str, database: str):
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.database = database

    def cypher(self, query: str) -> dict:
        url = f"{self.base_url}/db/data/cypher"
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "X-User": self.user,
                "X-Pass": self.password,
                "X-Database": self.database,
            },
            json={"statements": [{"query": query}]},
            timeout=180,
        )
        if not response.ok:
            raise RuntimeError(
                f"HTTP {response.status_code} from {url}: "
                f"{response.text[:1200]}"
            )

        data = response.json()
        if data.get("errors"):
            raise RuntimeError(
                "NexusDB returned query errors: "
                + json.dumps(data["errors"], ensure_ascii=False)
            )
        return data


def _entity_properties(value) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        return {"value": value}

    for key in ("properties", "props", "property"):
        props = value.get(key)
        if isinstance(props, dict):
            result = dict(props)
            if "id" in value and "_id" not in result:
                result["_id"] = value["id"]
            if "type" in value and "_type" not in result:
                result["_type"] = value["type"]
            if "labels" in value and "_labels" not in result:
                result["_labels"] = value["labels"]
            return result
    return dict(value)


def _node_frame(rows: list[dict], key: str, id_name: str) -> pd.DataFrame:
    result = []
    for row in rows:
        props = _entity_properties(row.get(key))
        if not props:
            continue
        item = dict(props)
        if id_name not in item:
            item[id_name] = item.get("external_id", item.get("_id"))
        result.append(item)
    return pd.DataFrame(result)


def _near_frame(rows: list[dict]) -> pd.DataFrame:
    result = []
    for row in rows:
        a = _entity_properties(row.get("a"))
        b = _entity_properties(row.get("b"))
        r = _entity_properties(row.get("r"))
        source_id = a.get("external_id", a.get("_id"))
        target_id = b.get("external_id", b.get("_id"))
        if source_id is None or target_id is None:
            continue
        result.append(
            {
                "source_id": str(source_id),
                "target_id": str(target_id),
                "distance_m": r.get("distance_m"),
            }
        )
    return pd.DataFrame(result)


def _located_frame(rows: list[dict]) -> pd.DataFrame:
    result = []
    for row in rows:
        p = _entity_properties(row.get("p"))
        b = _entity_properties(row.get("b"))
        poi_id = p.get("external_id", p.get("_id"))
        bairro_id = b.get("external_id", b.get("_id"))
        if poi_id is None or bairro_id is None:
            continue
        result.append(
            {
                "poi_id": str(poi_id),
                "bairro_id": str(bairro_id),
                "bairro_name": b.get("name", ""),
            }
        )
    return pd.DataFrame(result)


@st.cache_data(show_spinner="Lendo o grafo do NexusDB...", ttl=300)
def load_data(base_url: str, user: str, password: str, database: str):
    client = NexusClient(base_url, user, password, database)

    poi_result = client.cypher("MATCH (p:POI) RETURN p")
    bairro_result = client.cypher("MATCH (b:Bairro) RETURN b")
    near_result = client.cypher(
        "MATCH (a:POI)-[r:NEAR]->(b:POI) RETURN a, r, b"
    )
    located_result = client.cypher(
        "MATCH (p:POI)-[r:LOCATED_IN]->(b:Bairro) RETURN p, r, b"
    )

    pois = _node_frame(poi_result.get("resultados", []), "p", "poi_id")
    bairros = _node_frame(
        bairro_result.get("resultados", []), "b", "bairro_id"
    )
    near = _near_frame(near_result.get("resultados", []))
    located = _located_frame(located_result.get("resultados", []))

    if pois.empty:
        raise RuntimeError("Nenhum nó POI foi encontrado no banco informado.")

    for col in ("latitude", "longitude"):
        if col not in pois.columns:
            raise RuntimeError(
                f"POI sem propriedade obrigatória '{col}'. "
                f"Colunas disponíveis: {list(pois.columns)}"
            )
        pois[col] = pd.to_numeric(pois[col], errors="coerce")

    pois = pois.dropna(subset=["latitude", "longitude"]).copy()
    pois["poi_id"] = pois["poi_id"].astype(str)

    for col, default in (
        ("name", ""),
        ("category", "unknown"),
        ("bairro", ""),
        ("address", ""),
        ("cep", ""),
        ("source_layer", ""),
    ):
        if col not in pois.columns:
            pois[col] = default
        pois[col] = pois[col].fillna(default).astype(str)

    if not near.empty:
        near["source_id"] = near["source_id"].astype(str)
        near["target_id"] = near["target_id"].astype(str)
        near["distance_m"] = pd.to_numeric(
            near["distance_m"], errors="coerce"
        )

    if not located.empty:
        located["poi_id"] = located["poi_id"].astype(str)
        located["bairro_name"] = located["bairro_name"].fillna("").astype(str)

        # Prefer the graph relation as the normalized bairro name when present.
        bairro_by_poi = (
            located.dropna(subset=["poi_id"])
            .drop_duplicates("poi_id")
            .set_index("poi_id")["bairro_name"]
            .to_dict()
        )
        pois["bairro_graph"] = pois["poi_id"].map(bairro_by_poi).fillna("")
    else:
        pois["bairro_graph"] = ""

    pois["bairro_display"] = pois["bairro_graph"].where(
        pois["bairro_graph"].str.strip() != "", pois["bairro"]
    )
    pois["bairro_display"] = (
        pois["bairro_display"].replace("", "Sem bairro informado")
    )

    return pois, bairros, near, located


def build_graph(pois: pd.DataFrame, near: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()
    for _, row in pois.iterrows():
        graph.add_node(
            row["poi_id"],
            name=row["name"],
            category=row["category"],
            bairro=row["bairro_display"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
        )

    if not near.empty:
        for _, row in near.dropna(subset=["distance_m"]).iterrows():
            source_id = row["source_id"]
            target_id = row["target_id"]
            if (
                source_id in graph
                and target_id in graph
                and source_id != target_id
            ):
                graph.add_edge(
                    source_id,
                    target_id,
                    distance_m=float(row["distance_m"]),
                )
    return graph


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_008.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def format_distance(meters: float | None) -> str:
    if meters is None or pd.isna(meters):
        return "—"
    if meters < 1000:
        return f"{meters:,.0f} m".replace(",", ".")
    return f"{meters / 1000:,.2f} km".replace(",", "X").replace(".", ",").replace("X", ".")


def category_palette(categories: list[str]) -> dict[str, str]:
    colors = [
        "red",
        "blue",
        "green",
        "purple",
        "orange",
        "darkred",
        "cadetblue",
        "darkgreen",
        "darkpurple",
        "pink",
        "gray",
        "black",
    ]
    return {
        category: colors[i % len(colors)]
        for i, category in enumerate(sorted(categories))
    }


def poi_label(row: pd.Series) -> str:
    bairro = row.get("bairro_display", "")
    return f"{row['name']} | {row['category']} | {bairro} | {row['poi_id']}"


def make_map(
    filtered: pd.DataFrame,
    all_pois: pd.DataFrame,
    near: pd.DataFrame,
    graph: nx.Graph,
    show_edges: bool,
    max_edge_distance: float,
    selected_a: str | None,
    selected_b: str | None,
    show_graph_path: bool,
) -> tuple[folium.Map, dict]:
    if filtered.empty:
        center = [-22.8832, -43.1034]
    else:
        center = [
            float(filtered["latitude"].mean()),
            float(filtered["longitude"].mean()),
        ]

    # CARTO raster basemaps now require an API key.  Use the official
    # OpenStreetMap standard raster tiles instead, which do not require an API
    # key for normal interactive use.  Keep attribution visible as required by
    # the OSM tile usage policy.
    fmap = folium.Map(
        location=center,
        zoom_start=12,
        tiles=None,
        control_scale=True,
    )

    folium.TileLayer(
        tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="© OpenStreetMap contributors",
        name="OpenStreetMap",
        overlay=False,
        control=True,
        show=True,
        max_zoom=19,
    ).add_to(fmap)

    categories = sorted(filtered["category"].unique().tolist())
    palette = category_palette(categories)
    cluster = MarkerCluster(name="POIs filtrados").add_to(fmap)

    for _, row in filtered.iterrows():
        popup = folium.Popup(
            f"""
            <b>{row['name']}</b><br>
            <b>Categoria:</b> {row['category']}<br>
            <b>Bairro:</b> {row['bairro_display']}<br>
            <b>Endereço:</b> {row.get('address', '')}<br>
            <b>CEP:</b> {row.get('cep', '')}<br>
            <b>ID:</b> {row['poi_id']}<br>
            <b>Fonte:</b> {row.get('source_layer', '')}
            """,
            max_width=360,
        )
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            tooltip=f"{row['name']} · {row['category']}",
            popup=popup,
            icon=folium.Icon(
                color=palette.get(row["category"], "blue"),
                icon="info-sign",
            ),
        ).add_to(cluster)

    visible_ids = set(filtered["poi_id"])
    visible_edge_count = 0

    if show_edges and not near.empty:
        edge_layer = folium.FeatureGroup(
            name=f"NEAR ≤ {max_edge_distance:.0f} m",
            show=True,
        )
        lookup = all_pois.set_index("poi_id")
        subset = near[
            near["source_id"].isin(visible_ids)
            & near["target_id"].isin(visible_ids)
            & (near["distance_m"] <= max_edge_distance)
        ].copy()

        # Browser usability guard for dense graphs.
        if len(subset) > 3000:
            subset = subset.nsmallest(3000, "distance_m")

        for _, edge in subset.iterrows():
            a = lookup.loc[edge["source_id"]]
            b = lookup.loc[edge["target_id"]]
            folium.PolyLine(
                [
                    [a["latitude"], a["longitude"]],
                    [b["latitude"], b["longitude"]],
                ],
                weight=1,
                opacity=0.22,
                tooltip=f"NEAR: {format_distance(edge['distance_m'])}",
            ).add_to(edge_layer)
            visible_edge_count += 1
        edge_layer.add_to(fmap)

    distance_info = {
        "direct_m": None,
        "graph_m": None,
        "path": [],
        "visible_edges": visible_edge_count,
    }

    if selected_a and selected_b and selected_a != selected_b:
        lookup = all_pois.set_index("poi_id")
        if selected_a in lookup.index and selected_b in lookup.index:
            a = lookup.loc[selected_a]
            b = lookup.loc[selected_b]
            direct_m = haversine_m(
                float(a["latitude"]),
                float(a["longitude"]),
                float(b["latitude"]),
                float(b["longitude"]),
            )
            distance_info["direct_m"] = direct_m

            folium.PolyLine(
                [
                    [a["latitude"], a["longitude"]],
                    [b["latitude"], b["longitude"]],
                ],
                weight=4,
                opacity=0.85,
                color="red",
                dash_array="8,8",
                tooltip=f"Distância geodésica: {format_distance(direct_m)}",
            ).add_to(fmap)

            if show_graph_path and selected_a in graph and selected_b in graph:
                try:
                    path = nx.shortest_path(
                        graph,
                        selected_a,
                        selected_b,
                        weight="distance_m",
                    )
                    graph_m = nx.shortest_path_length(
                        graph,
                        selected_a,
                        selected_b,
                        weight="distance_m",
                    )
                    distance_info["graph_m"] = float(graph_m)
                    distance_info["path"] = path

                    path_coords = [
                        [
                            graph.nodes[node]["latitude"],
                            graph.nodes[node]["longitude"],
                        ]
                        for node in path
                    ]
                    folium.PolyLine(
                        path_coords,
                        weight=5,
                        opacity=0.9,
                        color="blue",
                        tooltip=(
                            "Menor caminho no grafo NEAR: "
                            f"{format_distance(graph_m)} · "
                            f"{len(path) - 1} arestas"
                        ),
                    ).add_to(fmap)
                except nx.NetworkXNoPath:
                    pass

    if not filtered.empty:
        bounds = [
            [filtered["latitude"].min(), filtered["longitude"].min()],
            [filtered["latitude"].max(), filtered["longitude"].max()],
        ]
        if bounds[0] != bounds[1]:
            fmap.fit_bounds(bounds, padding=(20, 20))

    folium.LayerControl(collapsed=False).add_to(fmap)
    return fmap, distance_info


def nearest_neighbors(
    selected_id: str,
    graph: nx.Graph,
    pois: pd.DataFrame,
    limit: int = 10,
) -> pd.DataFrame:
    if selected_id not in graph:
        return pd.DataFrame()

    lookup = pois.set_index("poi_id")
    rows = []
    for neighbor in graph.neighbors(selected_id):
        edge = graph[selected_id][neighbor]
        if neighbor not in lookup.index:
            continue
        poi = lookup.loc[neighbor]
        rows.append(
            {
                "nome": poi["name"],
                "categoria": poi["category"],
                "bairro": poi["bairro_display"],
                "distancia_m": float(edge.get("distance_m", math.nan)),
                "poi_id": neighbor,
            }
        )
    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .sort_values("distancia_m")
        .head(limit)
        .reset_index(drop=True)
    )


def main() -> None:
    st.set_page_config(
        page_title="NexusDB · Niterói Urban Graph",
        page_icon="🗺️",
        layout="wide",
    )

    st.title("NexusDB · Mapa Urbano Interativo de Niterói")
    st.caption(
        "Exemplo didático: dados persistidos no NexusDB, filtros espaciais, "
        "grafo de proximidade City2Graph e cálculo de distâncias."
    )

    with st.sidebar:
        st.header("Conexão NexusDB")
        base_url = st.text_input("URL", DEFAULT_URL)
        user = st.text_input("Usuário", DEFAULT_USER)
        password = st.text_input(
            "Senha",
            value=DEFAULT_PASSWORD,
            type="password",
        )
        database = st.text_input("Database", DEFAULT_DATABASE)
        if st.button("Atualizar dados", use_container_width=True):
            load_data.clear()

        st.divider()
        st.header("Sobre")
        st.info(
            "A relação NEAR foi criada por raio euclidiano no City2Graph. "
            "Ela representa proximidade, não uma rota de rua."
        )

    if not database:
        st.warning("Informe o nome do database NexusDB na barra lateral.")
        st.stop()

    if not password:
        st.warning("Informe a senha do NexusDB na barra lateral.")
        st.stop()

    try:
        pois, bairros, near, located = load_data(
            base_url,
            user,
            password,
            database,
        )
    except Exception as exc:
        st.error(f"Falha ao carregar o NexusDB: {exc}")
        st.stop()

    graph = build_graph(pois, near)

    st.subheader("Filtros")
    f1, f2, f3 = st.columns([1.2, 1.2, 1.8])

    category_options = sorted(pois["category"].unique().tolist())
    bairro_options = sorted(pois["bairro_display"].unique().tolist())

    with f1:
        categories = st.multiselect(
            "Categoria",
            category_options,
            placeholder="Todas as categorias",
        )
    with f2:
        bairros_selected = st.multiselect(
            "Bairro",
            bairro_options,
            placeholder="Todos os bairros",
        )
    with f3:
        search = st.text_input(
            "Buscar nome/endereço",
            placeholder="Ex.: hospital, escola, cultura...",
        ).strip()

    filtered = pois.copy()
    if categories:
        filtered = filtered[filtered["category"].isin(categories)]
    if bairros_selected:
        filtered = filtered[
            filtered["bairro_display"].isin(bairros_selected)
        ]
    if search:
        needle = search.casefold()
        mask = (
            filtered["name"].str.casefold().str.contains(needle, na=False)
            | filtered["address"].str.casefold().str.contains(needle, na=False)
            | filtered["poi_id"].str.casefold().str.contains(needle, na=False)
        )
        filtered = filtered[mask]

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("POIs exibidos", len(filtered))
    metric2.metric("POIs no banco", len(pois))
    metric3.metric("Categorias visíveis", filtered["category"].nunique())
    metric4.metric("Bairros visíveis", filtered["bairro_display"].nunique())

    st.subheader("Mapa")
    map_col, controls_col = st.columns([3.2, 1.15])

    with controls_col:
        st.markdown("#### Grafo e distância")
        show_edges = st.checkbox("Mostrar relações NEAR", value=False)

        if near.empty or near["distance_m"].dropna().empty:
            max_edge_distance = 1200.0
        else:
            max_available = float(near["distance_m"].max())
            max_edge_distance = st.slider(
                "Distância máxima das arestas",
                min_value=50.0,
                max_value=max(100.0, math.ceil(max_available / 50) * 50.0),
                value=min(1200.0, max_available),
                step=50.0,
                disabled=not show_edges,
            )

        selection_source = filtered if not filtered.empty else pois
        labels = {
            poi_label(row): row["poi_id"]
            for _, row in selection_source.sort_values("name").iterrows()
        }
        label_options = ["—"] + list(labels.keys())

        selected_label_a = st.selectbox("POI A", label_options, index=0)
        selected_label_b = st.selectbox("POI B", label_options, index=0)

        selected_a = labels.get(selected_label_a)
        selected_b = labels.get(selected_label_b)
        show_graph_path = st.checkbox(
            "Mostrar menor caminho no grafo NEAR",
            value=True,
        )

        if selected_a and selected_b and selected_a == selected_b:
            st.warning("Escolha dois POIs diferentes.")

    fmap, distance_info = make_map(
        filtered,
        pois,
        near,
        graph,
        show_edges,
        max_edge_distance,
        selected_a,
        selected_b,
        show_graph_path,
    )

    with map_col:
        st_folium(
            fmap,
            width=None,
            height=690,
            returned_objects=[],
        )

    if selected_a and selected_b and selected_a != selected_b:
        st.subheader("Comparação de distâncias")
        d1, d2, d3 = st.columns(3)
        d1.metric(
            "Distância geodésica",
            format_distance(distance_info["direct_m"]),
            help="Grande-círculo entre as coordenadas dos dois POIs.",
        )

        if distance_info["graph_m"] is not None:
            d2.metric(
                "Menor caminho em NEAR",
                format_distance(distance_info["graph_m"]),
                help=(
                    "Soma de distance_m nas relações NEAR. "
                    "Não representa distância viária."
                ),
            )
            d3.metric(
                "Arestas no caminho",
                max(0, len(distance_info["path"]) - 1),
            )
        else:
            d2.metric("Menor caminho em NEAR", "Sem caminho")
            d3.metric("Arestas no caminho", "—")

        st.caption(
            "A linha vermelha tracejada é a distância geodésica direta. "
            "A linha azul, quando disponível, é o menor caminho pelo grafo "
            "de proximidade NEAR."
        )

    if selected_a:
        st.subheader("Vizinhança do POI A")
        selected_row = pois.set_index("poi_id").loc[selected_a]
        c1, c2 = st.columns([1, 2])
        with c1:
            st.write(f"**Nome:** {selected_row['name']}")
            st.write(f"**Categoria:** {selected_row['category']}")
            st.write(f"**Bairro:** {selected_row['bairro_display']}")
            st.write(f"**Endereço:** {selected_row['address'] or '—'}")
            st.write(f"**Grau NEAR:** {graph.degree(selected_a) if selected_a in graph else 0}")
        with c2:
            neighbors = nearest_neighbors(selected_a, graph, pois)
            if neighbors.empty:
                st.info("Esse POI não possui vizinhos NEAR.")
            else:
                st.dataframe(
                    neighbors,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "distancia_m": st.column_config.NumberColumn(
                            "Distância (m)",
                            format="%.1f",
                        )
                    },
                )

    st.subheader("POIs filtrados")
    table = filtered[
        [
            "name",
            "category",
            "bairro_display",
            "address",
            "cep",
            "latitude",
            "longitude",
            "poi_id",
        ]
    ].rename(
        columns={
            "name": "Nome",
            "category": "Categoria",
            "bairro_display": "Bairro",
            "address": "Endereço",
            "cep": "CEP",
            "latitude": "Latitude",
            "longitude": "Longitude",
            "poi_id": "POI ID",
        }
    )
    st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        height=360,
    )

    st.download_button(
        "Baixar POIs filtrados em CSV",
        data=table.to_csv(index=False).encode("utf-8-sig"),
        file_name="niteroi_pois_filtrados.csv",
        mime="text/csv",
    )

    with st.expander("Como interpretar este exemplo"):
        st.markdown(
            """
            **NexusDB** é a fonte persistente do grafo. Os nós `POI` e
            `Bairro`, além das relações `NEAR` e `LOCATED_IN`, são
            lidos da API Cypher-like.

            **City2Graph** foi usado na etapa de construção para gerar
            proximidade por raio. Por isso, `NEAR` significa proximidade
            geométrica dentro do raio configurado, não uma rota de trânsito.

            **Distância geodésica** mede diretamente a separação entre dois
            pontos sobre a Terra. **Menor caminho NEAR** soma os pesos das
            arestas de proximidade do grafo. Comparar os dois valores ajuda a
            demonstrar a diferença entre distância espacial direta e
            conectividade estrutural.

            Para transformar este exemplo em análise real de acessibilidade,
            substitua ou complemente `NEAR` com rede viária, GTFS e
            metapaths de tempo de viagem.
            """
        )


if __name__ == "__main__":
    main()
