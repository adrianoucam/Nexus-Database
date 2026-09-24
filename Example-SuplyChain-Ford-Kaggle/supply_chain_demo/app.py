import os
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from risk_analysis import analyze_supply_risk
from graph_builder import make_html
from nexus_client import NexusClient

st.set_page_config(page_title='NexusDB Supply Chain', layout='wide')
st.title('NexusDB — Supply Chain Impact Analysis')
st.caption('Simulação what-if de retirada de fornecedor/produto e propagação de impacto.')


def add_node(nodes, label, key, props):
    key = str(key or '').strip()
    if not key:
        return None
    nid = f'{label}:{key}'
    nodes.setdefault(nid, {'id': nid, 'label': label, 'properties': props})
    return nid


def add_edge(edges, source, target, typ):
    if source and target:
        edges[(source, target, typ)] = {'source': source, 'target': target, 'type': typ}


@st.cache_data(show_spinner=False)
def load_csv(path, limit):
    df = pd.read_csv(path, dtype=str, nrows=limit or None).fillna('')
    nodes, edges = {}, {}
    for _, r in df.iterrows():
        sid = add_node(nodes, 'Supplier', r.SupplierID, {'supplier_id': r.SupplierID, 'name': r.SupplierName, 'address': r.SupplierAddress})
        pid = add_node(nodes, 'Product', r.ProductID, {'product_id': r.ProductID, 'car_maker': r.CarMaker, 'car_model': r.CarModel, 'color': r.CarColor, 'model_year': r.CarModelYear})
        cid = add_node(nodes, 'Customer', r.CustomerID, {'customer_id': r.CustomerID, 'name': r.CustomerName})
        oid = add_node(nodes, 'Order', r.OrderID, {'order_id': r.OrderID, 'order_date': r.OrderDate, 'ship_date': r.ShipDate, 'sales': r.Sales, 'quantity': r.Quantity})
        loc = add_node(nodes, 'Location', r.PostalCode, {'postal_code': r.PostalCode, 'city': r.City, 'state': r.State, 'country': r.Country})
        ship = add_node(nodes, 'ShippingMode', r.ShipMode, {'name': r.ShipMode, 'transport': r.Shipping})
        add_edge(edges, sid, pid, 'SUPPLIES')
        add_edge(edges, cid, oid, 'PLACED')
        add_edge(edges, oid, pid, 'CONTAINS')
        add_edge(edges, oid, ship, 'SHIPPED_VIA')
        add_edge(edges, oid, loc, 'DELIVERED_TO')
    return list(nodes.values()), list(edges.values()), df


def rows_as_dicts(cols, rows):
    return [{str(cols[i]): (row[i] if i < len(row) else '') for i in range(len(cols))} for row in rows]


def val(d, *names):
    # aceita nome exato e também diferenças de maiúsculas/minúsculas
    lower = {str(k).lower(): v for k, v in d.items()}
    for name in names:
        if name in d:
            return d[name]
        if name.lower() in lower:
            return lower[name.lower()]
    return ''


def load_nexus(url, user, password, database, limit):
    nx = NexusClient(url, user, password, database)
    nodes, edges = {}, {}
    raw_debug = {}
    lim = int(limit)

    # PRE-FLIGHT: exatamente UMA tentativa antes das consultas de carga.
    # Se usuário/senha estiverem errados, nenhuma das 5 consultas abaixo é executada.
    nx.authenticate_once()

    queries = {
        'supplies': f'MATCH (s:Supplier)-[:SUPPLIES]->(p:Product) RETURN s.supplier_id, s.name, p.product_id, p.car_maker, p.car_model LIMIT {lim}',
        'contains': f'MATCH (o:Order)-[:CONTAINS]->(p:Product) RETURN o.order_id, o.order_date, o.ship_date, o.sales, o.quantity, p.product_id, p.car_maker, p.car_model LIMIT {lim}',
        'placed': f'MATCH (c:Customer)-[:PLACED]->(o:Order) RETURN c.customer_id, c.name, o.order_id LIMIT {lim}',
        'shipping': f'MATCH (o:Order)-[:SHIPPED_VIA]->(m:ShippingMode) RETURN o.order_id, m.name, m.transport LIMIT {lim}',
        'location': f'MATCH (o:Order)-[:DELIVERED_TO]->(l:Location) RETURN o.order_id, l.postal_code, l.city, l.state, l.country LIMIT {lim}',
    }

    for qname, query in queries.items():
        try:
            cols, rows, payload = nx.query_rows(query)
            raw_debug[qname] = payload
        except Exception as exc:
            # Algumas versões ainda não aceitam todas as projeções. Mantém as relações já carregadas.
            raw_debug[qname] = {'error': str(exc), 'query': query}
            continue

        for d in rows_as_dicts(cols, rows):
            if qname == 'supplies':
                sidv = val(d, 's.supplier_id', 'supplier_id')
                pidv = val(d, 'p.product_id', 'product_id')
                sid = add_node(nodes, 'Supplier', sidv, {'supplier_id': sidv, 'name': val(d, 's.name', 'name')})
                pid = add_node(nodes, 'Product', pidv, {'product_id': pidv, 'car_maker': val(d, 'p.car_maker', 'car_maker'), 'car_model': val(d, 'p.car_model', 'car_model')})
                add_edge(edges, sid, pid, 'SUPPLIES')
            elif qname == 'contains':
                oidv = val(d, 'o.order_id', 'order_id')
                pidv = val(d, 'p.product_id', 'product_id')
                oid = add_node(nodes, 'Order', oidv, {'order_id': oidv, 'order_date': val(d, 'o.order_date', 'order_date'), 'ship_date': val(d, 'o.ship_date', 'ship_date'), 'sales': val(d, 'o.sales', 'sales'), 'quantity': val(d, 'o.quantity', 'quantity')})
                pid = add_node(nodes, 'Product', pidv, {'product_id': pidv, 'car_maker': val(d, 'p.car_maker', 'car_maker'), 'car_model': val(d, 'p.car_model', 'car_model')})
                add_edge(edges, oid, pid, 'CONTAINS')
            elif qname == 'placed':
                cidv = val(d, 'c.customer_id', 'customer_id')
                oidv = val(d, 'o.order_id', 'order_id')
                cid = add_node(nodes, 'Customer', cidv, {'customer_id': cidv, 'name': val(d, 'c.name', 'name')})
                oid = add_node(nodes, 'Order', oidv, {'order_id': oidv})
                add_edge(edges, cid, oid, 'PLACED')
            elif qname == 'shipping':
                oidv = val(d, 'o.order_id', 'order_id')
                name = val(d, 'm.name', 'name')
                oid = add_node(nodes, 'Order', oidv, {'order_id': oidv})
                mid = add_node(nodes, 'ShippingMode', name, {'name': name, 'transport': val(d, 'm.transport', 'transport')})
                add_edge(edges, oid, mid, 'SHIPPED_VIA')
            elif qname == 'location':
                oidv = val(d, 'o.order_id', 'order_id')
                postal = val(d, 'l.postal_code', 'postal_code')
                oid = add_node(nodes, 'Order', oidv, {'order_id': oidv})
                lid = add_node(nodes, 'Location', postal, {'postal_code': postal, 'city': val(d, 'l.city', 'city'), 'state': val(d, 'l.state', 'state'), 'country': val(d, 'l.country', 'country')})
                add_edge(edges, oid, lid, 'DELIVERED_TO')

    status = nx.cluster_status()
    # tabela amigável equivalente ao painel CSV
    records = []
    for n in nodes.values():
        p = n['properties']
        records.append({'Type': n['label'], 'ID': n['id'], **p})
    df = pd.DataFrame(records).fillna('')
    return list(nodes.values()), list(edges.values()), df, status, raw_debug


with st.sidebar:
    st.header('Fonte de dados')
    source = st.radio('Fonte', ['CSV', 'NexusDB'], horizontal=True, key='source')
    if source == 'CSV':
        csv_path = st.text_input('CSV', value=os.getenv('SUPPLY_CHAIN_CSV', 'Car_SupplyChainManagementDataSet.csv'))
        limit = st.number_input('Linhas para visualização', 100, 10000, 1000, 100, key='csv_limit')
    else:
        url = st.text_input('NexusDB URL', value=os.getenv('NEXUSDB_URL', 'http://127.0.0.1:7475'))
        database = st.text_input('Database', value=os.getenv('NEXUSDB_DATABASE', 'SUPPLY_CHAIN_TEST2'))
        user = st.text_input('Usuário', value=os.getenv('NEXUSDB_USER', 'admin'))
        password = st.text_input('Senha', type='password', value='', key='nexus_password')
        limit = st.number_input('Máximo por relação', 100, 20000, 5000, 100, key='nexus_limit')
        connect = st.button('Conectar / carregar grafo', type='primary', use_container_width=True)
        if st.session_state.get('nexus_loaded'):
            st.success('Grafo em memória. Alterar filtros não reconecta ao banco.')
            if st.button('Desconectar / limpar sessão', use_container_width=True):
                for k in ('nexus_loaded','nexus_nodes','nexus_edges','nexus_df','nexus_status','nexus_debug','nexus_connection'):
                    st.session_state.pop(k, None)
                st.rerun()

try:
    if source == 'CSV':
        nodes, edges, df = load_csv(csv_path, int(limit))
        status, raw_debug = {}, {}
    else:
        # IMPORTANTE: digitar senha, mudar selectbox, checkbox etc. NÃO acessa o NexusDB.
        # Só o clique explícito abaixo dispara autenticação/carga.
        if connect:
            if not password:
                st.error('Informe a senha do NexusDB antes de conectar.')
                st.stop()
            connection_key = (url.rstrip('/'), database, user, int(limit))
            with st.spinner('Autenticando uma vez e, se autorizado, carregando o grafo...'):
                try:
                    loaded = load_nexus(url, user, password, database, int(limit))
                except Exception as exc:
                    # Não mantém senha nem tenta outras consultas após falha no pre-flight.
                    st.session_state['nexus_loaded'] = False
                    st.error(f'Conexão/autenticação interrompida após a primeira tentativa: {exc}')
                    st.info('Nenhuma consulta adicional de carga foi executada após a falha inicial.')
                    st.stop()
            nodes, edges, df, status, raw_debug = loaded
            st.session_state['nexus_nodes'] = nodes
            st.session_state['nexus_edges'] = edges
            st.session_state['nexus_df'] = df
            st.session_state['nexus_status'] = status
            st.session_state['nexus_debug'] = raw_debug
            st.session_state['nexus_connection'] = connection_key
            st.session_state['nexus_loaded'] = True
        elif st.session_state.get('nexus_loaded'):
            nodes = st.session_state['nexus_nodes']
            edges = st.session_state['nexus_edges']
            df = st.session_state['nexus_df']
            status = st.session_state.get('nexus_status', {})
            raw_debug = st.session_state.get('nexus_debug', {})
        else:
            st.info('Informe os dados e clique em “Conectar / carregar grafo”. Nenhuma tentativa de login foi feita ainda.')
            st.stop()

        if not nodes:
            st.error('Conectou ao NexusDB, mas nenhuma relação pôde ser convertida em nós. Abra “Diagnóstico NexusDB” abaixo.')
            with st.expander('Diagnóstico NexusDB', expanded=True):
                st.json(raw_debug)
            st.stop()
except Exception as e:
    st.error(f'Não foi possível carregar os dados: {e}')
    st.stop()

if source == 'NexusDB':
    role = status.get('role') or status.get('status', {}).get('role') or 'desconhecido'
    st.success(f'NexusDB carregado em memória — database {database} · role {role} · {len(nodes)} nós · {len(edges)} relações')
    st.caption('Filtros e simulações abaixo usam st.session_state e não fazem novo login.')
    with st.expander('Diagnóstico NexusDB / JSON bruto'):
        st.json({'cluster_status': status, 'queries': raw_debug})

left, right = st.columns([0.42, 0.58], gap='large')

byid = {str(n["id"]): n for n in nodes}

def display(n):
    p = n.get("properties", {})
    return (
        p.get("name")
        or " — ".join(
            filter(None, [p.get("car_maker"), p.get("car_model"), p.get("product_id")])
        )
        or n["id"]
    )

with left:
    st.subheader("Simulação e risco")
    available_kinds = [
        k for k in ("Supplier", "Product")
        if any(n["label"] == k for n in nodes)
    ]
    if not available_kinds:
        st.error("Não há Supplier/Product disponíveis para a simulação.")
        st.stop()

    kind = st.selectbox("Retirar", available_kinds)
    candidates = [n for n in nodes if n["label"] == kind]
    selected = st.selectbox("Elemento", candidates, format_func=display)
    focus = st.checkbox("Mostrar somente rede afetada", value=True)

    result = analyze_supply_risk(nodes, edges, selected["id"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Risk Score", f'{result["risk_score"]:.1f}/100')
    c2.metric("Nível", result["risk_level"])
    c3.metric("Resiliência", result["resilience"])

    tabs = st.tabs(["Impacto", "Risco", "Alternativas", "Caminhos afetados"])

    with tabs[0]:
        a, b, c = st.columns(3)
        a.metric("Produtos bloqueados", len(result["blocked_products"]))
        b.metric("Produtos em risco", len(result["at_risk_products"]))
        c.metric("Pedidos expostos", len(result["affected_orders"]))

        a, b = st.columns(2)
        a.metric("Clientes expostos", len(result["affected_customers"]))
        b.metric("Quantidade exposta", f'{result["quantity_exposed"]:,.0f}')

        st.metric("Receita potencialmente exposta", f'{result["revenue_exposed"]:,.2f}')

        rows = []
        for label, key in [
            ("REMOVIDO", "removed"),
            ("BLOQUEADO", "blocked"),
            ("EM RISCO", "at_risk"),
        ]:
            for nid in result[key]:
                n = byid.get(str(nid))
                if n:
                    rows.append({
                        "status": label,
                        "tipo": n["label"],
                        "elemento": display(n),
                        "id": nid,
                    })
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            height=260,
            hide_index=True,
        )

    with tabs[1]:
        st.markdown("#### Componentes do Risk Score")
        comp_df = pd.DataFrame([
            {
                "componente": name,
                "valor_normalizado": round(value, 3),
                "peso": weight,
                "contribuição": round(value * weight * 100, 2),
            }
            for (name, value), weight in zip(
                result["components"].items(),
                [0.30, 0.25, 0.20, 0.15, 0.10],
            )
        ])
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

        st.progress(min(1.0, result["risk_score"] / 100.0))
        st.caption(
            "Score demonstrativo = 30% dependência + 25% pedidos + "
            "20% receita + 15% clientes + 10% centralidade."
        )

        r1, r2 = st.columns(2)
        r1.metric(
            "Dependência exclusiva",
            f'{result["exclusive_ratio"] * 100:.1f}%'
        )
        r2.metric(
            "Alternativas médias/produto",
            f'{result["avg_alternatives"]:.2f}'
        )

        r1, r2 = st.columns(2)
        r1.metric("Grau do nó", result["selected_degree"])
        r2.metric(
            "Centralidade de grau",
            f'{result["degree_centrality"]:.3f}'
        )

        st.info(
            "Os pesos e limiares são parâmetros de demonstração. "
            "Em uso real devem ser calibrados com histórico de ruptura, "
            "lead time, criticidade, estoque, SLA e custos."
        )

    with tabs[2]:
        alt_rows = []
        for pid in sorted(result["blocked_products"] | result["at_risk_products"]):
            product = byid.get(pid, {})
            alternatives = result["alternative_suppliers"].get(pid, [])
            if kind == "Product":
                # Para retirada do próprio produto, fornecedores são contexto,
                # não substitutos do produto.
                status_txt = "PRODUTO INDISPONÍVEL"
            else:
                status_txt = "ALTERNATIVA OBSERVADA" if alternatives else "SEM ALTERNATIVA"

            alt_names = [
                display(byid[sid]) if sid in byid else sid
                for sid in alternatives
            ]
            alt_rows.append({
                "produto": display(product) if product else pid,
                "status": status_txt,
                "fornecedores alternativos": ", ".join(alt_names) or "—",
                "qtd alternativas": len(alternatives),
            })

        if alt_rows:
            st.dataframe(
                pd.DataFrame(alt_rows),
                use_container_width=True,
                height=280,
                hide_index=True,
            )
        else:
            st.info("Não foram encontradas alternativas para este cenário.")

        st.caption(
            "“Alternativa” significa outro Supplier ligado ao mesmo Product "
            "no dataset. Não garante capacidade, prazo, homologação ou estoque."
        )

    with tabs[3]:
        path_rows = []
        for i, path in enumerate(result["paths"], 1):
            labels = []
            for nid in path:
                n = byid.get(str(nid))
                labels.append(
                    f'{n["label"]}: {display(n)}' if n else str(nid)
                )
            path_rows.append({
                "#": i,
                "caminho de impacto": "  →  ".join(labels),
                "saltos": max(0, len(path) - 1),
            })

        if path_rows:
            st.dataframe(
                pd.DataFrame(path_rows),
                use_container_width=True,
                height=300,
                hide_index=True,
            )
        else:
            st.info("Nenhum caminho afetado encontrado.")

    st.subheader("Dados " + ("do NexusDB" if source == "NexusDB" else "do dataset"))
    st.dataframe(df.head(100), use_container_width=True, height=250, hide_index=True)

with right:
    st.subheader("Grafo de dependências")
    components.html(
        make_html(nodes, edges, result, focus),
        height=760,
        scrolling=False,
    )

    st.markdown("#### Resumo executivo do cenário")
    if result["risk_level"] in ("CRÍTICO", "ALTO"):
        st.error(
            f'Risco {result["risk_level"]}: {len(result["blocked_products"])} '
            f'produto(s) bloqueado(s), {len(result["affected_orders"])} pedido(s) '
            f'e {len(result["affected_customers"])} cliente(s) exposto(s).'
        )
    elif result["risk_level"] == "MODERADO":
        st.warning(
            f'Risco MODERADO: existem dependências relevantes, com '
            f'{len(result["at_risk_products"])} produto(s) em risco.'
        )
    else:
        st.success(
            "Risco BAIXO no modelo atual; o grafo observado apresenta "
            "impacto limitado para este cenário."
        )

    st.caption(
        "A análise representa dependências observadas no dataset. "
        "Não equivale a uma BOM industrial. Para afirmar continuidade real "
        "de produção, acrescente Component/REQUIRES, estoque, lead time, "
        "capacidade, homologação e fornecedores substitutos."
    )
