# NexusDB AirRoute Resilience V1.6 — Multi-hop Route Explorer

Dashboard Streamlit para demonstrar **Property Graph + Graph Analytics + Geospatial + Resiliência** usando o NexusDB.

## Pipeline nativo confirmado

```text
/db/data/cypher
      ↓
data.rs
      ↓
graph_routes.rs
      ↓
graph_algorithms.rs
      ↓
GraphView / CSR
```

O pacote **não contém mais o patch de roteamento da V1.4**, porque a versão atual
do NexusDB já encaminha os `CALL algo.*` por `graph_routes.rs`.

## CALLs usados

```cypher
CALL algo.degree() LIMIT 20000;
CALL algo.pageRank(20) LIMIT 200;
CALL algo.connectedComponents();
CALL graph.statistics();
CALL algo.shortestPath(start_id, end_id);
```

O `LIMIT 20000` de Degree é proposital: além do ranking, a V1.5 usa o resultado
para mapear `Airport.airport_id` para o ID interno do NexusDB exigido por
`shortestPath`. A tabela visual mostra apenas o Top 20.

## O que aparece no dashboard

- query `CALL` efetivamente enviada;
- engine identificado como `NexusDB / CSR`;
- tempo observado pelo cliente para Degree;
- tempo observado pelo cliente para PageRank;
- tempo observado pelo cliente para Connected Components;
- tempo observado pelo cliente para graph.statistics;
- Degree do aeroporto selecionado;
- PageRank do aeroporto quando estiver no Top 200;
- quantidade e tamanho do maior componente;
- shortest path nativo com IDs internos, quantidade de saltos e caminho retornado;
- `ST_DWithin`/RTree para aeroportos em um raio configurável;
- operador materializado × inferido × não resolvido;
- mapa, conectividade e simulação de resiliência.

### Interpretação do tempo

O tempo mostrado é medido no Streamlit ao redor da chamada HTTP. Portanto inclui:

```text
requisição HTTP
+ execução no NexusDB
+ serialização JSON
+ transferência da resposta
```

Ele não deve ser descrito como tempo puro de CPU do algoritmo.

## Geospatial

O filtro é executado no NexusDB:

```cypher
MATCH (a:Airport)
WHERE ST_DWithin(a, lon, lat, distancia_em_graus)
RETURN a
LIMIT 500
```

A implementação atual usa o índice espacial/RTree e distância em unidades da
geometria. Para SRID 4326, a V1.5 converte aproximadamente `km / 111.32` para o
pré-filtro e aplica Haversine aos candidatos apenas para refinar e apresentar a
distância em quilômetros.

## Executar

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Configuração típica:

```text
URL:      http://127.0.0.1:7475
Database: OPENFLIGHTS_TEST
User:     admin
```

## Observação sobre o dataset

OpenFlights representa conectividade declarada. O dashboard não interpreta as
rotas como disponibilidade, frequência, preço ou operação de voo em tempo real.


## Correção V1.5.1

A V1.5 tinha uma colisão de nomes em Python:

```python
import streamlit.components.v1 as components
...
components = native["components"]
...
components.html(...)
```

A variável local substituía o módulo `streamlit.components.v1`, produzindo:

```text
AttributeError: 'dict' object has no attribute 'html'
```

A V1.5.1 renomeia o resultado para `components_result`, restaurando a renderização
do property graph PyVis. Também adiciona visualizações Airport-only dos rankings,
sem recalcular os algoritmos: Degree/PageRank continuam sendo executados no
NexusDB/CSR sobre o grafo completo.


## V1.6 — Planejador Multi-hop

A nova aba **Planejador Multi-hop** remove a restrição de origem brasileira.

É possível selecionar:

- qualquer aeroporto de origem;
- um aeroporto específico como destino; ou
- qualquer aeroporto de um país como destino;
- de 1 a 6 níveis/trechos.

Semântica:

```text
1 nível  = origem → destino                 (direto)
2 níveis = origem → conexão → destino       (1 conexão)
3 níveis = origem → conexão → conexão → destino
...
```

Exemplo:

```text
Paraguay → Portugal
ASU → ... → LIS/OPO/...
```

A busca de itinerários usa exclusivamente a conectividade declarada nos nós
`Route` (`source_airport_id` → `destination_airport_id`). Isso é intencional:
o CSR global do NexusDB é heterogêneo e também contém Country, Airline,
AircraftType e Route; esses nós não devem ser interpretados como escalas de voo.

Quando o destino é um aeroporto específico e Graph Analytics já foi executado,
a aba também permite comparar o caminho semântico Airport→Airport com:

```cypher
CALL algo.shortestPath(source_internal_id, target_internal_id);
```

Assim a aplicação demonstra simultaneamente duas visões:

1. **route planning semântico**, específico do domínio aéreo;
2. **shortest path nativo NexusDB/CSR**, sobre o property graph completo.

OpenFlights representa conectividade declarada, não disponibilidade de voo em
tempo real, frequência, preço ou bilhete combinável.

## Correção V1.6.1 — mapa

A V1.6 desenhava todas as alternativas simultaneamente. A V1.6.1 mostra,
por padrão, somente o itinerário selecionado. A sobreposição das demais
alternativas passou a ser opcional. Também invalida resultados antigos quando
origem, destino ou profundidade são alterados e mostra os países de cada trecho.
