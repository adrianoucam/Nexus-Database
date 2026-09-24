# NexusDB Supply Chain Explorer

## Análise de Cadeias de Suprimentos com Banco de Dados Orientado a Grafos


![Texto Alternativo](imagem1.png)

Este projeto demonstra a utilização do **NexusDB**, um banco de dados
orientado a grafos desenvolvido em **Rust**, para modelagem, exploração
e análise de uma cadeia de suprimentos.

O exemplo utiliza um dataset de **Supply Chain** obtido no Kaggle e
transforma os registros originalmente tabulares em uma estrutura de
**Property Graph**.

A proposta é demonstrar como informações distribuídas entre
fornecedores, materiais, produtos, fábricas, centros de distribuição,
clientes e fluxos logísticos podem ser representadas como uma **rede de
dependências**.

> **Nota sobre o dataset:** este projeto utiliza o dataset disponível no
> diretório `SuplyChain-Ford-Kaggle` como base experimental. Os
> resultados representam os dados presentes no conjunto utilizado e não
> devem ser interpretados automaticamente como uma representação
> completa ou atual da cadeia de suprimentos real de uma empresa.

------------------------------------------------------------------------

## 1. Por que Supply Chain é um problema de grafos?

Uma cadeia de suprimentos não é apenas um conjunto de registros. Ela é,
essencialmente, uma rede de entidades conectadas.

``` text
Fornecedor
     │
     ▼
  Material
     │
     ▼
   Produto
     │
     ▼
   Fábrica
     │
     ▼
Centro de Distribuição
     │
     ▼
   Cliente
```

Em muitos casos, a informação mais importante não está em uma entidade
isolada, mas nas relações existentes entre diferentes entidades.

Perguntas típicas incluem:

-   quais produtos dependem de determinado fornecedor?
-   quais fornecedores participam de determinado produto?
-   quantos níveis existem entre um fornecedor e o produto final?
-   quais nós concentram grande quantidade de dependências?
-   existem caminhos alternativos?
-   o que acontece com a rede se um fornecedor ficar indisponível?
-   quais entidades podem ser afetadas por uma interrupção?
-   existem componentes isolados na cadeia?

Esse tipo de análise apresenta forte aderência a bancos de dados
orientados a grafos.

------------------------------------------------------------------------

## 2. Objetivo

O objetivo deste exemplo é demonstrar como o NexusDB pode ser utilizado
para:

-   representar uma Supply Chain como **Property Graph**;
-   identificar fornecedores e dependências;
-   acompanhar relacionamentos entre materiais, produtos e unidades;
-   descobrir caminhos entre entidades;
-   analisar dependências de múltiplos níveis;
-   identificar nós altamente conectados;
-   localizar elementos estruturalmente importantes;
-   estudar componentes conectados;
-   analisar o impacto da indisponibilidade de elementos;
-   explorar caminhos alternativos;
-   executar algoritmos de Graph Analytics diretamente no NexusDB.

O projeto também serve como caso de uso e ambiente experimental para
avaliar o NexusDB em uma rede diferente dos exemplos tradicionais de
redes sociais.

------------------------------------------------------------------------

## 3. Dataset

Os dados utilizados são provenientes de um dataset público de **Supply
Chain disponibilizado no Kaggle**.

O conjunto original possui estrutura predominantemente tabular. Durante
a preparação dos dados, registros podem ser transformados em entidades e
relacionamentos de um grafo.

Conceitualmente, informações tabulares semelhantes a:

``` text
Fornecedor | Material | Produto | Unidade | Destino | Transporte | ...
```

podem ser convertidas em:

``` text
(:Supplier)
      │
      │ SUPPLIES
      ▼
(:Material)
      │
      │ USED_IN
      ▼
(:Product)
      │
      │ PRODUCED_AT
      ▼
(:Facility)
      │
      │ SHIPPED_TO
      ▼
(:Destination)
```

A estrutura efetivamente importada depende das colunas existentes no
dataset e das regras utilizadas pelo processo de transformação.

------------------------------------------------------------------------

## 4. Modelo conceitual do grafo

Uma Supply Chain pode ser representada por um modelo como:

``` text
                    ┌──────────────┐
                    │   Supplier   │
                    └──────┬───────┘
                           │
                       SUPPLIES
                           │
                           ▼
                    ┌──────────────┐
                    │   Material   │
                    └──────┬───────┘
                           │
                        USED_IN
                           │
                           ▼
                    ┌──────────────┐
                    │   Product    │
                    └──────┬───────┘
                           │
                      PRODUCED_AT
                           │
                           ▼
                    ┌──────────────┐
                    │   Facility   │
                    └──────┬───────┘
                           │
                      SHIPPED_TO
                           │
                           ▼
                  ┌──────────────────┐
                  │ Distribution Hub │
                  └────────┬─────────┘
                           │
                      DELIVERED_TO
                           │
                           ▼
                    ┌──────────────┐
                    │   Customer   │
                    └──────────────┘
```

Dependendo dos atributos disponíveis, outras entidades e relações podem
ser incorporadas.

------------------------------------------------------------------------

## 5. Property Graph

O NexusDB utiliza o conceito de **Property Graph**.

Nós podem possuir propriedades:

``` text
(:Supplier {
    supplier_id: "...",
    name: "...",
    country: "..."
})
```

Relacionamentos também podem carregar informações:

``` text
(:Supplier)-[:SUPPLIES {
    quantity: ...,
    lead_time: ...,
    cost: ...
}]->(:Material)
```

Quando esses atributos estiverem disponíveis no dataset, podem ser
preservados na transformação.

Assim, o grafo pode representar não apenas:

``` text
A está relacionado com B
```

mas também informações sobre **como**, **quando** e **sob quais
propriedades** essa relação ocorre.

------------------------------------------------------------------------

## 6. Banco relacional e banco orientado a grafos

Em uma estrutura relacional, uma análise de cadeia de suprimentos pode
exigir a combinação de várias tabelas:

``` text
Supplier
    JOIN
Material
    JOIN
Product
    JOIN
Facility
    JOIN
Shipment
    JOIN
Customer
```

No modelo orientado a grafos, os relacionamentos fazem parte diretamente
da estrutura:

``` text
Supplier
   │
   ├──► Material
   │       │
   │       └──► Product
   │                │
   │                └──► Facility
   │                         │
   │                         └──► Distribution
   │                                  │
   │                                  └──► Customer
```

Isso torna natural a exploração de perguntas baseadas em conectividade,
dependências e caminhos.

O objetivo não é substituir bancos relacionais em todos os cenários.
Bancos relacionais e bancos orientados a grafos atendem a necessidades
diferentes e podem coexistir na mesma arquitetura.

------------------------------------------------------------------------

## 7. NexusDB no projeto

A arquitetura conceitual do exemplo é:

``` text
Dataset Kaggle
      │
      ▼
Transformação / Importação
      │
      ▼
   NexusDB
      │
      ├──────── Property Graph
      │
      ├──────── CSR
      │
      ├──────── Degree
      │
      ├──────── PageRank
      │
      ├──────── Connected Components
      │
      └──────── Shortest Path
      │
      ▼
Supply Chain Application
      │
      ▼
Visualização e análise
```

O NexusDB atua como camada de persistência do grafo e também como
mecanismo de consulta e análise estrutural da rede.

------------------------------------------------------------------------

## 8. Graph Analytics

O NexusDB disponibiliza algoritmos nativos que podem ser aplicados ao
grafo da Supply Chain.

### Degree

``` cypher
CALL algo.degree();
```

O Degree permite identificar nós com grande quantidade de conexões.

Em uma Supply Chain, essa métrica pode auxiliar na identificação de
entidades que concentram muitos relacionamentos.

``` text
             Supplier
           /    |    \
          /     |     \
     Product Product Product
```

Um Degree elevado não significa automaticamente que o elemento seja
crítico. Ele representa uma característica estrutural que deve ser
analisada junto ao contexto do negócio.

------------------------------------------------------------------------

## 9. PageRank

``` cypher
CALL algo.pageRank(20);
```

O PageRank permite analisar a importância estrutural de um nó
considerando também as conexões dos elementos relacionados.

Em uma rede de Supply Chain, isso oferece uma perspectiva complementar à
simples contagem de relacionamentos.

------------------------------------------------------------------------

## 10. Connected Components

``` cypher
CALL algo.connectedComponents();
```

Connected Components permite identificar como o grafo está dividido em
grupos conectados.

Exemplo:

``` text
Rede principal
     │
     └──────── milhares de entidades

Componente isolado A
     │
     └──────── conjunto independente

Componente isolado B
     │
     └──────── outro conjunto
```

A presença de componentes isolados pode ser relevante tanto para a
análise da rede quanto para a identificação de possíveis problemas de
integração ou modelagem dos dados.

------------------------------------------------------------------------

## 11. Shortest Path

O NexusDB permite procurar caminhos entre nós:

``` cypher
CALL algo.shortestPath(source_id, target_id);
```

Isso permite analisar como duas entidades estão conectadas dentro da
rede.

``` text
Fornecedor A
      │
      ▼
 Material X
      │
      ▼
 Produto Y
      │
      ▼
  Unidade Z
```

Em um grafo heterogêneo, o resultado deve ser interpretado considerando
os tipos de nós e relacionamentos presentes no modelo.

------------------------------------------------------------------------

## 12. CSR --- Compressed Sparse Row

Os algoritmos nativos de Graph Analytics do NexusDB utilizam uma
representação baseada em **CSR --- Compressed Sparse Row**.

``` text
Property Graph
      │
      ▼
  Graph View
      │
      ▼
     CSR
      │
      ├── Degree
      ├── PageRank
      ├── Connected Components
      └── Shortest Path
```

CSR é uma representação compacta da estrutura de adjacência de um grafo,
adequada para operações de travessia e algoritmos de redes.

Isso permite utilizar o mesmo ambiente para armazenar o Property Graph e
executar análises sobre sua estrutura.

------------------------------------------------------------------------

## 13. Dependências de múltiplos níveis

Uma das aplicações mais importantes do modelo de grafos em Supply Chain
é a análise **multi-hop**.

Considere:

``` text
Supplier A
    │
    ▼
Component B
    │
    ▼
Assembly C
    │
    ▼
Product D
    │
    ▼
Plant E
```

Uma consulta de primeiro nível mostra:

``` text
Supplier A → Component B
```

Uma exploração com maior profundidade permite observar:

``` text
Supplier A
   ↓
Component B
   ↓
Assembly C
   ↓
Product D
   ↓
Plant E
```

Isso é relevante porque uma dependência ou risco pode estar vários
níveis distante do produto final.

------------------------------------------------------------------------

## 14. Análise de impacto

Considere:

``` text
Supplier A ──► Component X ──┐
                             │
Supplier B ──► Component Y ──┼──► Product P
                             │
Supplier C ──► Component Z ──┘
```

Se `Supplier B` ficar indisponível, podemos investigar quais elementos
possuem dependência direta ou indireta dele.

``` text
               Supplier B
                    │
                    X
               indisponível
                    │
                    ▼
              Component Y
                    │
                    ▼
               Product P
                    │
                    ▼
              downstream
```

O grafo permite explorar os níveis seguintes e identificar as entidades
potencialmente alcançadas pela interrupção.

------------------------------------------------------------------------

## 15. Resiliência da cadeia

Outra aplicação é comparar a estrutura antes e depois da remoção lógica
de determinado nó.

``` text
Grafo original

A ─── B ─── C ─── D
      │
      E
      │
      F


Removendo B

A     C ─── D

      E
      │
      F
```

Dependendo da topologia, a remoção pode:

-   fragmentar componentes;
-   eliminar caminhos;
-   isolar entidades;
-   aumentar distâncias entre pontos;
-   revelar dependências sem alternativas.

Isso permite utilizar o grafo como base para experimentos de
**resiliência da cadeia de suprimentos**.

------------------------------------------------------------------------

## 16. Identificação de pontos críticos

A combinação de diferentes métricas pode auxiliar na investigação de
elementos estruturalmente relevantes.

Por exemplo:

``` text
                   Supply Chain
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
      Degree         PageRank        Components
        │               │                │
        └───────────────┼────────────────┘
                        ▼
               análise estrutural
                        │
                        ▼
             investigação de risco
```

Nenhuma dessas métricas deve ser interpretada isoladamente como uma
medida definitiva de risco operacional.

Elas funcionam como instrumentos para identificar pontos que merecem
análise adicional.

------------------------------------------------------------------------

## 17. Caminhos alternativos

Considere duas possibilidades para alcançar determinado produto ou
unidade:

``` text
Supplier A ──► Component X ──► Product P

Supplier B ──► Component Y ──► Product P
```

A existência de diferentes caminhos no grafo pode ser utilizada para
investigar redundância estrutural.

Em modelos mais completos, atributos como custo, prazo, capacidade ou
risco podem ser incorporados aos relacionamentos e utilizados como
pesos.

------------------------------------------------------------------------

## 18. Vantagens do modelo orientado a grafos para Supply Chain

  -----------------------------------------------------------------------
  Característica                      Aplicação em Supply Chain
  ----------------------------------- -----------------------------------
  Relacionamentos explícitos          fornecedores, materiais e produtos
                                      permanecem conectados

  Multi-hop                           análise de fornecedores e
                                      dependências em vários níveis

  Shortest Path                       descoberta de caminhos entre
                                      entidades

  Degree                              identificação de concentração de
                                      conexões

  PageRank                            análise de importância estrutural

  Connected Components                identificação de fragmentação

  Traversal                           exploração upstream e downstream

  Property Graph                      propriedades em nós e
                                      relacionamentos

  CSR                                 processamento da estrutura de
                                      adjacências

  Impact Analysis                     estudo dos efeitos da remoção de
                                      elementos

  Resilience Analysis                 investigação de caminhos e
                                      dependências alternativas
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 19. Aplicações possíveis

A arquitetura pode ser expandida para diferentes problemas.

``` text
Supplier Risk
        │
        ├── dependência de fornecedores
        ├── fornecedores únicos
        └── concentração

Logistics
        │
        ├── centros de distribuição
        ├── rotas
        └── caminhos alternativos

Manufacturing
        │
        ├── componentes
        ├── produtos
        └── plantas

Resilience
        │
        ├── falha de fornecedores
        ├── interrupção logística
        └── fragmentação da rede

Graph Analytics
        │
        ├── Degree
        ├── PageRank
        ├── Components
        └── Shortest Path
```

------------------------------------------------------------------------

## 20. Executando o exemplo

Com o NexusDB iniciado, configure a aplicação com o endpoint
correspondente à sua instalação.

Exemplo:

``` text
URL:       http://127.0.0.1:7475
Database:  SUPPLY_CHAIN
User:      admin
```

Instale as dependências do exemplo:

``` bash
python -m pip install -r requirements.txt
```

Execute a aplicação:

``` bash
python -m streamlit run app.py
```

Os nomes dos arquivos e comandos podem variar conforme a versão da
aplicação presente neste diretório.

------------------------------------------------------------------------

## 21. Fluxo sugerido para demonstração

``` text
Dataset Supply Chain
        │
        ▼
Importar para o NexusDB
        │
        ▼
Visualizar Property Graph
        │
        ▼
Selecionar fornecedor/produto
        │
        ▼
Explorar relacionamentos
        │
        ▼
Analisar dependências multi-hop
        │
        ▼
Degree / PageRank
        │
        ▼
Connected Components
        │
        ▼
Shortest Path
        │
        ▼
Simular indisponibilidade
        │
        ▼
Avaliar impacto
        │
        ▼
Investigar caminhos alternativos
```

------------------------------------------------------------------------

## 22. Exemplo de perguntas para a aplicação

Depois da importação, o grafo pode ser utilizado para investigar
questões como:

``` text
Quais produtos estão relacionados a este fornecedor?

Quais fornecedores estão relacionados a este produto?

Qual é a vizinhança de primeiro nível deste nó?

Quais dependências aparecem no segundo ou terceiro nível?

Qual é o caminho entre duas entidades?

Quais nós apresentam maior Degree?

Quais nós apresentam maior PageRank?

Quantos componentes conectados existem?

Qual é o impacto estrutural da retirada deste nó?

A remoção fragmenta a rede?

Existem outros caminhos entre origem e destino?
```

------------------------------------------------------------------------

## 23. Limitações

Este projeto é uma demonstração de **Graph Database + Graph Analytics**.

Os resultados dependem diretamente da cobertura, qualidade e estrutura
do dataset utilizado.

Uma relação existente no grafo significa que ela foi construída a partir
das informações disponíveis no conjunto de dados. Ela não deve ser
automaticamente interpretada como uma representação completa e atual de
uma cadeia de suprimentos real.

Da mesma forma, Degree, PageRank, Shortest Path e Connected Components
são medidas estruturais do grafo. Sua interpretação como risco,
criticidade, dependência comercial ou impacto operacional exige
informações e critérios adicionais do domínio.

------------------------------------------------------------------------

## 24. Possíveis evoluções

O exemplo abre espaço para novas funcionalidades no NexusDB e na
aplicação:

-   Betweenness Centrality;
-   Community Detection;
-   `k-shortest paths`;
-   caminhos ponderados;
-   custo logístico como peso;
-   lead time como peso;
-   risco de fornecedor como peso;
-   análise temporal da Supply Chain;
-   comparação entre cenários;
-   propagação de risco;
-   detecção de Single Points of Failure;
-   simulação de interrupções;
-   recomendação de fornecedores alternativos;
-   Graph Machine Learning;
-   integração com dados geoespaciais;
-   mapas de fornecedores, fábricas e rotas;
-   análise de mudanças estruturais ao longo do tempo.

------------------------------------------------------------------------

## 25. Tecnologias

Este exemplo utiliza conceitos e tecnologias como:

-   **NexusDB**
-   **Rust**
-   **Property Graph**
-   **CSR --- Compressed Sparse Row**
-   **Graph Analytics**
-   **Python**
-   **Streamlit**
-   **Kaggle Dataset**
-   **Supply Chain Analytics**
-   **Network Analysis**

------------------------------------------------------------------------

## 26. Sobre o NexusDB

O **NexusDB** é um projeto de banco de dados orientado a grafos
desenvolvido em Rust.

Este projeto demonstra uma das aplicações possíveis da tecnologia:
utilizar relacionamentos como parte central da representação e análise
dos dados.

A mesma abordagem pode ser explorada em outros domínios:

``` text
Supply Chain
Transportation
Bioinformatics
Fraud Detection
Cybersecurity
Knowledge Graphs
Social Networks
Infrastructure Networks
Recommendation Systems
```

A proposta dos projetos de exemplo é demonstrar o NexusDB em problemas
reais e datasets de diferentes áreas, indo além de grafos sintéticos.

------------------------------------------------------------------------

## 27. Contribuições

Sugestões, testes, Issues e contribuições são bem-vindos.

Se este projeto for útil para seus estudos ou experimentos:

-   ⭐ deixe uma estrela no repositório;
-   acompanhe as próximas versões;
-   abra uma Issue para relatar problemas ou sugerir funcionalidades;
-   contribua com novos casos de uso, datasets e benchmarks.

------------------------------------------------------------------------

## NexusDB

**Graph Database + Graph Analytics + Rust**

Transformando relacionamentos em estruturas diretamente analisáveis.
