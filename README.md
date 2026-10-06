# NexusDB — instalador Windows
![alt text]("Logo NexusDB com Rede Neon.png")
## Download da versao 0.1.1

- [Instalador Windows x64](https://github.com/adrianoucam/Nexus-Database/releases/download/v0.1.1/NexusDB-0.1.1-windows-x64-setup.exe)
- [SHA-256](https://github.com/adrianoucam/Nexus-Database/releases/download/v0.1.1/NexusDB-0.1.1-windows-x64-setup.exe.sha256)
- [Notas da versao](installer/RELEASE-0.1.1.md)

O pacote tambem esta em [output](output/). Inclui o executavel com suporte CUDA,
a DLL CUDA, manuais e ferramenta de backup/restore. O projeto e experimental.

## CUDA e processamento paralelo na CPU

O NexusDB 0.1.1 inclui processamento paralelo de Degree e PageRank em um pool
compartilhado de threads Rayon. Esse paralelismo utiliza varios nucleos da CPU
dentro do processo do servidor; nao distribui uma consulta entre processos ou
nos do cluster. PageRank tambem possui implementacao GPU via CUDA no Windows x64.

| Backend | Degree | PageRank |
|---|---|---|
| `CPU_SERIAL` | CPU serial | CPU serial |
| `CPU_PARALLEL` | Pool Rayon | Pool Rayon |
| `CUDA` | Erro `CUDA_UNSUPPORTED_OPERATION` | GPU NVIDIA, ou erro se indisponivel |
| `AUTO` | CPU serial ou paralela | CPU ou CUDA conforme tamanho e disponibilidade |

No arquivo do servico `C:\ProgramData\NexusDB\config\nexusdb.env`, coloque as
secoes abaixo depois das variaveis existentes, substituindo configuracoes
`NEXUSDB_COMPUTE_*` equivalentes:

```ini
[compute]
backend = "AUTO"
threads = 12
memory_mb = 512
max_jobs = 2
timeout_ms = 300000

[compute.cuda]
enabled = true
```

Reinicie o servico apos editar. Variaveis do ambiente do processo tem prioridade
sobre o arquivo. `threads` limita o pool CPU, `memory_mb` limita a reserva
estimada de trabalho dos algoritmos (nao o RSS total), `max_jobs` limita trabalhos
simultaneos e `timeout_ms` define o prazo cooperativo de cada chamada.

`AUTO` considera CUDA para PageRank com pelo menos 100 mil vertices, 1 milhao
de arestas e 10 iteracoes. Se a GPU estiver indisponivel, usa CPU. Grafos menores
podem executar na CPU mesmo com CUDA habilitado. `enabled = false` impede CUDA;
o backend explicito `CUDA` e estrito e nao faz fallback.

O campo `execution` das respostas informa `requested_backend`,
`selected_backend`, motivo, fallback e tempos. Consulte esse campo para confirmar
o backend realmente usado; habilitar CUDA nao comprova que uma consulta usou GPU.
Nao ha promessa de aceleracao sem medir a carga real.

```sql
CALL algo.degree();
CALL algo.pageRank(100);
```

Para compilar executavel e DLL juntos: `build_once_windows.bat release cuda`.
O instalador inclui ambos e usa runtime CUDA estatico. Para executar na GPU,
e necessario dispositivo NVIDIA compativel com compute capability 7.5 ou superior
e driver compativel com o Toolkit usado no build. O Toolkit e Visual Studio C++
Build Tools sao necessarios para compilar a DLL, nao para usar o pacote pronto.
Sem GPU, `AUTO` continua funcionando na CPU. Detalhes: [compute](Docs/COMPUTE_CPU.md).


## Instalacao e atualizacao

Execute o instalador como Administrador. Ele registra o Windows Service sob
`LocalService`, instala os binarios em `C:\Program Files\NexusDB\bin` e cria
configuracao, dados, backups e logs em `C:\ProgramData\NexusDB`.
A escuta padrao e `127.0.0.1:7474`. Novas instalacoes usam `AUTO`.

Atualizacoes param e reiniciam o servico e preservam a configuracao existente.
A senha solicitada serve para bootstrap; nao redefine a senha de um banco ja
inicializado. A desinstalacao preserva dados, configuracao, backups e logs.

## Reempacotar o instalador

Este repositorio e de distribuicao e nao inclui os fontes Rust do servidor.
Com Inno Setup 6 ou 7, disponibilize `target/release/nexusdb.exe` compilado com
suporte CUDA e `target/release/nexusdb_cuda.dll`, e execute:

```bat
build_installer_windows.bat
```

Se os fontes, Cargo.toml e o diretorio cuda estiverem presentes, o script
compila servidor e DLL antes de empacotar. Nesse caso, Rust, CUDA Toolkit e
Visual Studio C++ Build Tools tambem sao necessarios. O resultado fica em
`installer/output`. `installer/nexusdb.iss` e o script principal; `nexusdb.iss`
da raiz oferece o mesmo pacote com os caminhos relativos ajustados.

## Backup e administracao

O aplicativo [backup_app](backup_app/README.md) requer Python 3.10+ na maquina
onde for utilizado. O servidor nao depende de Python. Consulte tambem
[usuarios e permissoes SQL](Docs/SQL_USERS_AND_GRANTS.md) e [seguranca](SECURITY.md).
Usuarios e permissoes SQL sao locais a cada no do cluster.



GraphRAG and vector search
NexusDB includes native vector search designed to work together with the graph engine. This combination enables GraphRAG-style retrieval: a semantic search finds the most relevant entry points and graph traversal expands those results through explicit relationships before the context is sent to an LLM.

A typical flow is:

Question
   |
   v
Embedding
   |
   v
vector.search()
   |
   v
Relevant Chunk / Document
   |
   v
Graph traversal
   |
   +--> entities
   +--> events
   +--> suppliers
   +--> contracts
   +--> scientific relations
   +--> evidence
   |
   v
Structured context
   |
   v
LLM answer
This is useful when the answer is not contained in a single document. A normal RAG pipeline can retrieve semantically similar text, but GraphRAG can continue from that text into the graph and recover relationships that should not be inferred only from language similarity.

Why GraphRAG is useful
The main advantage is the separation between semantic relevance and structural evidence.

vector search finds documents, chunks or entities related to the question;
graph traversal follows explicit relationships stored in NexusDB;
graph algorithms can add structural measures such as degree, PageRank, connected components, shortest paths or communities;
the final context can preserve provenance and evidence paths instead of giving the LLM only a flat list of text chunks;
multi-hop questions can be answered using information distributed across several nodes and documents;
relationships can be reported without incorrectly converting association into causality.
For example, a supply-chain assistant may answer that a supplier is associated with an affected component without claiming that the supplier caused a delay unless the graph contains evidence that supports that conclusion.

Native vector search
Vector indexes are created over a node label and an embedding property:

CALL vector.createIndex(
  'document_embeddings',
  'Chunk',
  'embedding',
  384,
  'cosine'
)
A vector query can then retrieve the nearest nodes:

CALL vector.search(
  'document_embeddings',
  [0.013, -0.081, 0.117, 0.042],
  10,
  128
)
The final argument is the HNSW ef_search value.

NexusDB currently uses a hybrid strategy for the native vector engine: small indexes can use exact search, while larger indexes use HNSW approximate nearest neighbor search. This keeps small GraphRAG workloads deterministic while allowing larger collections to scale with an ANN index.

In a local benchmark with 10,000 normalized vectors and k=10, HNSW showed the following recall/latency behavior. These numbers are development benchmark results and should not be treated as universal performance guarantees:

ef_search   mean Recall@10   minimum Recall@10   p50 client latency
16              95.0%              70.0%               60.22 ms
32              95.2%              70.0%               61.25 ms
64              96.2%              70.0%               60.38 ms
128             97.0%              70.0%               62.23 ms
256             98.6%              80.0%               60.41 ms
512            100.0%             100.0%               62.01 ms
The same experiment measured about 141 ms median for a brute-force Python ground-truth implementation. This comparison is useful as a regression test, but it is not a Rust-vs-Rust performance comparison.

Example: supply-chain delay analysis
Suppose the text search retrieves a chunk associated with order PED-1057. The graph can then expand the context:

Document
   |
   v
Order
   |
   v
Production lot
   |
   +--> Operational event
   |
   v
Component
   |
   v
Supplier
A user can ask:

Why is order PED-1057 delayed, which component is involved, which supplier is associated with it, and which other orders may be exposed to the same issue?

The vector step locates the relevant document. The graph step can then recover the order, lot, event, component and supplier relationships and also search for other orders connected to the same component or production dependency.

The important distinction is that the graph can safely state that a supplier is associated with the affected component. It should only state that the supplier caused the delay when that causal relationship is explicitly supported by stored evidence.

Example: contracts and dependency risk
GraphRAG is also useful for questions whose answer requires several hops:

Supplier
   |
   +--> supplies Component A
   |          |
   |          +--> used by Product 1 --> Contract A
   |          |
   |          +--> used by Product 7 --> Contract B
   |
   +--> supplies Component B --> Product 9 --> Contract C
A question such as:

Which customer contracts could be affected if supplier X stops delivering?

cannot be answered reliably from one text chunk alone. Vector retrieval can identify the supplier or incident documentation, while graph traversal resolves the dependency chain.

Example: scientific and biomedical knowledge
A scientific GraphRAG can connect unstructured literature with a biological knowledge graph:

Article --> Gene --> Protein --> Gene --> Disease
             |
             +--> interaction evidence
For example:

Which proteins connect TP53 to disease X, and which publications support the relationships?

Vector retrieval can find relevant papers or abstracts and the graph can identify multi-hop biological paths. Evidence nodes can retain the publication or source that supports each relationship.

This model is particularly useful for protein-protein interaction datasets, literature exploration and hypothesis generation. The graph should still be treated as an evidence structure, not as proof of biological causality.

Example: organizational knowledge
An enterprise graph may combine:

Documents
Emails
Tickets
ERP records
Contracts
Projects
Employees
Products
Suppliers
Machines
Policies
GraphRAG can answer questions such as:

Which projects and customers are exposed to the incident described in this maintenance ticket?

The semantic retriever finds the ticket and related documents, while the graph resolves explicit dependencies between machines, projects, products, contracts and customers.

Example: provenance and investigative research
GraphRAG can also be used when every relationship should be traceable to an evidence source:

Person --RELATED_TO--> Person
   |                      |
   |                      +--> CANDIDATE_IN --> Election
   |
   +--> CANDIDATE_IN --> Election
   |
   +--> MEMBER_OF --> Party

Relationship --> EVIDENCED_BY --> Document / source
This supports questions that combine entity resolution, relationship discovery and documentary provenance. It is especially useful when the system must distinguish a confirmed relationship from a hypothesis that still requires manual review.

GraphRAG design principle
The intended architecture is:

Vector Search
     +
Graph traversal
     +
Graph algorithms
     +
Evidence / provenance
     |
     v
Grounded context
     |
     v
LLM
The LLM is not expected to invent graph relationships. NexusDB supplies the retrieved nodes, paths, metrics and evidence, and the language model is used to interpret and explain that context.

This makes GraphRAG most valuable for domains where the question includes who is connected to whom, through what path, because of which event, and supported by which evidence.

Executable graphs
O módulo público nexusdb::execution move a orquestração de agentes para o motor Rust. Ele oferece:

nós Splitter, Worker, Code, Gate e Human;
arestas dependency, correction, learning e approval;
condições por status, existência e igualdade usando JSON Pointer;
cálculo de ready_nodes e despacho paralelo por ondas;
retries configuráveis com evidências estruturadas por tentativa;
gates determinísticos para exit code, JSON Schema básico, testes e aprovação humana;
aprendizado de restrições após a sequência falha, correção e sucesso;
identificação das camadas Data, Knowledge e Execution;
executores desacoplados por meio do trait NodeExecutor;
APIs put_execution_graph, get_execution_graph, run_execution_graph e approve_execution_node na fachada NexusDB.
Chamadas de LLM e execução de scripts não são habilitadas implicitamente. Cada integração precisa registrar um adaptador em ExecutorRegistry. Consulte Docs/EXECUTION_GRAPHS.md para o modelo e os limites atuais.




