# NexusDB

Hospital longitudinal: [exemplo com 20 pacientes sintéticos, proveniência, ACL e histórico](examples/hospital_longitudinal-Example/README.md),
inspirado metodologicamente no artigo *Synthetic Hospital*.

Guia MCP: [manual ajustado ao NexusDB](MANUAL_MCP_NEXUSDB.md) e
[exemplos de descoberta, consultas e LLM local](examples/mcp-Example/README.md).

Livro em português: [NexusDB na prática](LIVRO_NEXUSDB.md), com três capítulos
(iniciante, intermediário e avançado), integração com IA/MCP/RAG/GraphRAG e
[catálogo dos programas de exemplo](LIVRO_NEXUSDB_CATALOGO.md).

Laboratórios executáveis: [API key, NPL e IA/GraphRAG acadêmicos](examples/academico_api_ia-Example/README.md),
com testes reais isolados e guia de consumo por chave.

NexusDB is an experimental graph database written in Rust, with a Cypher-like
HTTP API, spatial operations, SQLite-backed persistence, and an experimental
multi-node replication mode. It also includes native executable graphs for
agent/workflow orchestration, deterministic validation, evidence tracking and
constraint learning.

> **Project status: experimental.** This release is suitable for study,
> demonstrations, and controlled local testing. The HA layer is not a complete
> Raft implementation and must not be presented as production-grade consensus.

## NPL/pg v0.15 — integração experimental

O endpoint autenticado `POST /db/npl` permite registrar rotinas, executar `CALL`
e leituras `EXECUTE CYPHER` com parâmetros tipados e permissões do banco.
Inclui reservas cooperativas de memória e bibliotecas experimentais de cache
HOT/WARM/COLD e coordenação de consistência. O cache permanece separado das
consultas automáticas; escrita transacional NPL e ACID completo não estão disponíveis.
Veja [instalação, exemplos, validação e limitações](tools/npl_v015/README.md).

## Runtime adaptativo e recursos compartilhados — 08/10/2026

O NexusDB agora persiste o perfil de hardware e uma tabela empírica de custos
para Degree/PageRank. `AUTO` combina calibração exata, medições compatíveis e as
heurísticas existentes, sem executar benchmarks ocultos nas consultas.

- `nexusdb tune`: benchmark sintético de CPU/CUDA, snapshot/CSR e HNSW.
- Cache central de snapshots versionados, com proteção de referências em uso.
- Orçamento host compartilhado e remoção de caches ociosos sob pressão.
- Quotas configuráveis por classe em `[resources.*]`.
- Telemetria de cache frio/quente e reconstrução de índices vetoriais.
- `/agent/functions` e `/agent/function`: adaptador de funções sobre o Tool Registry.

```sql
CALL algo.tuningStats();
CALL db.resources.stats();
```

A gestão de memória cobre estruturas gerenciadas, não todo o RSS ou a VRAM.
As quotas são de admissão, sem fila ponderada. O adaptador não implementa uma
API completa de LLM. Configuração, escopo e testes:
[Runtime adaptativo](Docs/ADAPTIVE_RUNTIME.md).

## Melhorias atuais — Agent Tools (07/10/2026)

A atualização remove o bloqueio de consultas de metadados pelo tamanho do grafo
e permite configurar os limites do Agent Executor no arquivo do serviço.
O caso `BIOGRID_HUMAN` revelou a restrição anterior: `database.stats` retornava
HTTP 413 antes de executar quando o grafo excedia o orçamento de admissão.

### O que foi implementado

| Melhoria | Comportamento atual |
|---|---|
| Metadados sem admissão pelo tamanho do grafo | `database.stats` e `database.schema` não são bloqueados pela contagem de nós, relacionamentos ou estimativa de memória do grafo. |
| Nova ferramenta `database.schema` | Expõe a visualização nativa de schema pela API Agent, incluindo labels e tipos de relacionamentos. |
| Limites configuráveis | A seção `[agent]` controla nós, relacionamentos, memória estimada, concorrência, timeout e tamanho da resposta. |
| Orçamento herdado | Campos omitidos no `budget` HTTP recebem os limites configurados no servidor; o cliente pode solicitar valores menores. |
| Discovery com limites | `GET /agent/tools` publica `limits`, além das definições das ferramentas. |
| Diagnóstico de admissão | Erros de tamanho do grafo informam contagens, estimativa de memória e limites aplicados. |
| Cliente de teste atualizado | O smoke test herda os limites, ajusta o timeout HTTP pelo discovery, reconhece `status="success"` e interrompe após falhas. |
| Configuração da URL | O cliente tolera aspas externas acidentais na URL e valida o endereço antes da chamada HTTP, sem alterar senhas. |

A isenção de metadados mantém autenticação, autorização por database, verificação
da existência do banco, concorrência, timeout e limites de saída. As rotinas nativas
ainda percorrem os dados; a isenção não significa custo constante nem memória ilimitada.
As APIs e os comandos Cypher existentes continuam disponíveis.

### Configuração para um grafo maior

No arquivo do serviço, normalmente
`C:\ProgramData\NexusDB\config\nexusdb.env`, adicione a seção abaixo ou atualize
a existente. Os valores são um exemplo de capacidade, não uma medição do BIOGRID:

```ini
[agent]
timeout_ms = 60000
max_jobs = 2
max_nodes = 1000000
max_relationships = 10000000
max_memory_mb = 512
max_result_rows = 1000
max_result_bytes = 1048576
```

Sem configuração, os padrões são 10.000 ms, 2 trabalhos, 50.000 nós,
200.000 relacionamentos, 64 MiB estimados, 100 linhas e 1.048.576 bytes de saída.
Também são aceitas variáveis `NEXUSDB_AGENT_<CAMPO_EM_MAIUSCULAS>`, por exemplo
`NEXUSDB_AGENT_MAX_NODES`. Valores devem ser positivos; o cliente não pode elevar
seu orçamento acima dos limites do servidor.

A admissão de memória estima `256 × nós + 64 × relacionamentos` bytes.
Não representa o consumo total de RAM do processo, propriedades ou caches.
`max_result_bytes` limita o resultado nativo, sem incluir o envelope HTTP.

Agent e compute têm limites independentes. Para o teste de PageRank, revise a
seção `[compute]` existente com `backend = "AUTO"`, memória e timeout adequados
à máquina; prevalece o menor prazo efetivo. Não duplique seções ou chaves.
Instale o executável atualizado e reinicie o serviço para aplicar a configuração.

### Repetir o teste no BIOGRID_HUMAN

O script atualizado está no diretório local
`E:\nexusDB-tests\Agent-Examples`; ele é externo a este repositório.
Com as credenciais válidas já configuradas em `NEXUSDB_USER` e `NEXUSDB_PASSWORD`,
execute no CMD:

```bat
cd /d E:\nexusDB-tests\Agent-Examples
set "NEXUSDB_URL=http://127.0.0.1:7474"
set "NEXUSDB_DATABASE=BIOGRID_HUMAN"
python3 01_agent_tools_smoke.py --iterations 20 --limit 10
```

O banco deve existir. `--limit 10` limita a saída do PageRank, não o grafo analisado.
Consulte `result.execution` para identificar o backend escolhido e os tempos.
`AUTO` pode selecionar CPU serial, CPU paralela ou CUDA conforme heurísticas,
calibração e disponibilidade. Habilitar CUDA ou aumentar o grafo não garante uso da GPU.
CPU paralela usa threads Rayon no processo do servidor, não múltiplos processos.

### Validação e estado de entrega

- 58 testes unitários e um teste integrado HTTP passaram nesta atualização.
- Os testes cobrem a isenção de metadados, admissão de PageRank, limites maiores
  configurados e rejeição de orçamentos acima do permitido.
- O smoke test foi validado com HTTP simulado, incluindo herança de orçamento e timeout.
- O executável `target/release/nexusdb.exe` foi compilado com `--features cuda`.
  Esse build não comprova execução na GPU nem substitui a compilação/instalação da DLL CUDA.
- Registros locais: `target/agent-limits-test.log` e `target/agent-release-build.log`.
- O serviço instalado não foi substituído durante esta atualização. A execução
  real no `BIOGRID_HUMAN` e a medição CPU/CUDA permanecem pendentes.

Contratos e limites detalhados: [Agent Tools](Docs/TOOL_REGISTRY.md).
Outras melhorias já descritas abaixo incluem caches por database, planos GRASP,
telemetria, busca vetorial, GraphRAG e seleção de backend.

## Demonstração acadêmica de CRUD

O exemplo [Campus em grafos](examples/crud_academico-Example/README.md) oferece uma
interface no navegador para cadastrar, consultar, editar e excluir alunos,
professores e disciplinas, além de criar matrículas e visualizar relações
com setas e seleção de vizinhos. Usa Python sem dependências externas e
persiste as operações no NexusDB em um banco exclusivo `ACADEMICO_DEMO`.
Inclui dados fictícios, roteiro de aula e teste integrado com servidor isolado.
Agora inclui salas, turmas, séries, currículo e disponibilidade semanal, grade
com validação de conflitos e sugestões automáticas de horários para revisão.
O gerador é uma heurística limitada, sem garantia de solução ótima.

```bat
cd /d E:\nexusdb\examples\crud_academico-Example
python3 app.py --create --database ACADEMICO_DEMO --user administrador2
```

A senha é solicitada no terminal. Nas próximas execuções, omita `--create`.

## Build and run

### Agent Tools — primeiro MVP

`GET /agent/tools` e `POST /agent/tool/{name}` expõem seis ferramentas de leitura:
`database.stats`, `database.schema`, `graph.shortest_path`, `algo.pagerank`, `vector.search` e
`spatial.nearby`. Reutilizam autenticação e executores nativos, com validação,
admissão limitada e timeout. Veja [contratos e limitações](Docs/TOOL_REGISTRY.md)
e o [cliente de exemplo](examples/agent-tools-Example/README.md). MCP e tracing agentic
completo continuam pendentes.

Planejamento de versões futuras: [TO DO — skills e recursos agentic](TODO.md).
O Tool Registry tem o MVP descrito acima; MCP, supervisor e os demais itens não
concluídos continuam como propostas. O registro na lista não implica disponibilidade.

### Busca vetorial e GraphRAG

O núcleo HNSW nativo oferece `vector.createIndex`, `vector.listIndexes`,
`vector.search` e `vector.dropIndex`. `graphRAG.retrieve` combina sementes
vetoriais e evidências do grafo. Definições são persistidas por database;
índices derivados são reconstruídos quando os dados mudam. Veja
[sintaxe, limites e testes](Docs/VECTOR_HNSW_GRAPHRAG.md).

### Caches, telemetria e seleção de backend

MATCH agora usa identidade exata de consultas, cache de AST por database e cache
de planos físicos GRASP com invalidação por revisão do engine. Consulte métricas
com `CALL db.query.stats()`. Administradores podem medir CPU/CUDA com
`CALL algo.calibrate('pageRank', 100, 5)`; `AUTO` reutiliza a escolha para o mesmo
snapshot e número de iterações. Veja [configuração, limites e testes](Docs/QUERY_RUNTIME.md).

### CUDA e processamento paralelo na CPU

O NexusDB 0.1.1 inclui processamento paralelo de Degree e PageRank em um pool
compartilhado de threads Rayon. Esse paralelismo utiliza varios nucleos da CPU
dentro do processo do servidor; nao distribui uma consulta entre processos ou
nos do cluster. Degree e PageRank tambem possuem implementacao GPU via CUDA no Windows x64.

| Backend | Degree | PageRank |
|---|---|---|
| `CPU_SERIAL` | CPU serial | CPU serial |
| `CPU_PARALLEL` | Pool Rayon | Pool Rayon |
| `CUDA` | GPU NVIDIA, ou erro se indisponivel | GPU NVIDIA, ou erro se indisponivel |
| `AUTO` | CPU ou CUDA conforme perfil calibrado/heurística e disponibilidade | CPU ou CUDA conforme perfil calibrado/heurística e disponibilidade |

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

### Compilacao do servidor

Rust 1.85 or newer is recommended.

```powershell
$env:NEXUSDB_ADMIN_PASSWORD = "replace-with-a-long-unique-password"
$env:NEXUSDB_MODE = "SINGLE"
cargo run --release
```

Use `Ctrl+C` to request a graceful shutdown. NexusDB stops accepting new
connections, waits for active requests, stops its maintenance threads, and
performs a final flush/checkpoint before the process exits. A configuration
file can be loaded with `nexusdb run --config C:\path\nexusdb.env`.

The server listens on `127.0.0.1:7474` by default. Use
`NEXUSDB_HTTP_ADDR` only when you understand the exposure. NexusDB does not
terminate TLS; put a trusted TLS reverse proxy in front of it for remote use.
Direct non-loopback binding additionally requires the explicit
`NEXUSDB_ALLOW_INSECURE_REMOTE=true` acknowledgement.

The first start creates the persistent configuration database under
`NEXUSDB_DATA_ROOT` (default `data`). Passwords are hashed with Argon2id.
Backups use `NEXUSDB_BACKUP_ROOT` (default `<data-root>/backups`). If
`NEXUSDB_LOG_FILE` is configured, console and service messages are written to
that file and rotated at 10 MiB, retaining five files by default. Adjust this
with `NEXUSDB_LOG_MAX_BYTES` and `NEXUSDB_LOG_FILES`.

## HA laboratory mode

HA defaults to authenticated cluster messages and strict write quorum. Set a
different 32+ character secret on every cluster deployment and the same value
on all its nodes:

```powershell
$env:NEXUSDB_MODE = "HA"
$env:NEXUSDB_HA_SECRET = "replace-with-at-least-32-random-characters"
$env:NEXUSDB_HA_SERVER_ID = "1"
$env:NEXUSDB_HA_ALLOW_SINGLE_NODE_LEADER = "0"
```

Keep cluster links private or tunnel them through TLS. See [SECURITY.md](SECURITY.md).

### Eleição, failover e quorum

Em um cluster de três nós, dois membros formam quorum. Se o leader cair, os
dois followers restantes detectam a ausência de heartbeat e realizam uma nova
eleição. Com os valores padrão, isso normalmente leva entre quatro e cinco
segundos.

Use estas opções para impedir que um único nó isolado aceite escritas e cause
split-brain:

```text
NEXUSDB_HA_CLUSTER_AUTH=true
NEXUSDB_HA_STRICT=true
NEXUSDB_HA_ALLOW_SINGLE_NODE_LEADER=false
```

Se apenas um dos três membros permanecer ativo, ele não terá quorum e rejeitará
escritas. O HA do NexusDB é experimental e não implementa todas as garantias de
Raft.

### Recuperação automática de um nó

Um nó HA reiniciado nunca reutiliza automaticamente um papel `LEADER`
persistido. Ele volta como follower indisponível e executa o seguinte fluxo:

1. consulta `/cluster/health` nos peers e encontra o leader atual;
2. envia seu `last_log_index` para `/cluster/sync`;
3. aplica em ordem as entradas WAL ausentes;
4. instala snapshots de todos os databases quando o WAL não cobre a lacuna ou
   ultrapassa o limite de 5.000 entradas;
5. atualiza `last_log_index`, `commit_index` e `leader_id`;
6. torna-se um follower pronto somente após concluir o catch-up.

Durante a recuperação, `/cluster/health` retorna `"health":"SYNCING"` e
`"ready":false`. Requisições normais recebem HTTP 503; as rotas internas
`/cluster/*` permanecem disponíveis para concluir a sincronização.

### Cluster em máquinas diferentes

Os membros não precisam executar no mesmo servidor. O protocolo HA funciona
por HTTP e aceita peers em máquinas distintas. Por exemplo:

```text
node 1: 192.168.1.21:7474
node 2: 192.168.1.22:7474
node 3: 192.168.1.23:7474
```

Como cada máquina possui seu próprio endereço, todos os nós podem utilizar a
mesma porta. O node 1 pode ser configurado assim:

```text
NEXUSDB_MODE=HA
NEXUSDB_HA_SERVER_ID=1
NEXUSDB_HTTP_ADDR=0.0.0.0:7474
NEXUSDB_HA_PEERS=http://192.168.1.22:7474,http://192.168.1.23:7474
NEXUSDB_HA_CLUSTER_AUTH=true
NEXUSDB_HA_STRICT=true
NEXUSDB_HA_READ_REPLICAS=true
NEXUSDB_HA_ALLOW_SINGLE_NODE_LEADER=false
NEXUSDB_ALLOW_INSECURE_REMOTE=true
NEXUSDB_DATA_ROOT=data/node1
```

No node 2, altere os identificadores e peers:

```text
NEXUSDB_HA_SERVER_ID=2
NEXUSDB_HTTP_ADDR=0.0.0.0:7474
NEXUSDB_HA_PEERS=http://192.168.1.21:7474,http://192.168.1.23:7474
NEXUSDB_DATA_ROOT=data/node2
```

No node 3:

```text
NEXUSDB_HA_SERVER_ID=3
NEXUSDB_HTTP_ADDR=0.0.0.0:7474
NEXUSDB_HA_PEERS=http://192.168.1.21:7474,http://192.168.1.22:7474
NEXUSDB_DATA_ROOT=data/node3
```

Cada processo deve receber exatamente o mesmo segredo HA, com pelo menos 32
caracteres:

```powershell
$env:NEXUSDB_HA_SECRET = "replace-with-at-least-32-random-characters"
```

Requisitos operacionais para uma implantação distribuída:

- liberar a porta TCP escolhida somente entre os membros e clientes
  autorizados;
- manter os relógios das máquinas sincronizados, pois mensagens com diferença
  superior a 30 segundos são rejeitadas;
- utilizar armazenamento local independente em cada nó;
- configurar e rotacionar as credenciais administrativas em cada máquina,
  pois usuários ainda não são replicados pelo protocolo experimental;
- usar rede privada, VPN ou túnel/proxy TLS. O HMAC autentica mensagens do
  cluster, mas não criptografa o tráfego;
- nunca expor diretamente as portas do banco à internet;
- manter `NEXUSDB_HA_ALLOW_SINGLE_NODE_LEADER=false` para evitar split-brain.

`NEXUSDB_ALLOW_INSECURE_REMOTE=true` é uma confirmação explícita exigida pelo
servidor ao escutar fora do loopback; ela não torna a conexão segura. A
proteção deve ser fornecida pela rede privada ou camada TLS externa.

Em máquinas diferentes, inicie cada nó com seu próprio arquivo `.conf` e
script. O `run_cluster_ha.bat` abre três processos locais e, portanto, serve
apenas para a topologia de laboratório em um único Windows.

O failover, a eleição e o catch-up por WAL/snapshot utilizam os endereços de
`NEXUSDB_HA_PEERS` e funcionam da mesma forma na topologia distribuída.

### Consultar o leader

O health check não exige autenticação:

```powershell
curl http://127.0.0.1:7474/cluster/health
curl http://127.0.0.1:7475/cluster/health
curl http://127.0.0.1:7476/cluster/health
```

O leader apresenta `"role":"LEADER"`, `"ready":true` e seu `leader_id`. O
endpoint detalhado exige credenciais administrativas:

```powershell
curl -H "X-User: admin" -H "X-Pass: SUA_SENHA" http://127.0.0.1:7474/cluster/leader
```

Para consultar as três portas no CMD:

```bat
for %p in (7474 7475 7476) do @echo Porta %p & curl -s http://127.0.0.1:%p/cluster/health & echo.
```

Em um arquivo `.bat`, substitua `%p` por `%%p`.

## Executable graphs

O módulo público `nexusdb::execution` move a orquestração de agentes para o
motor Rust. Ele oferece:

- nós `Splitter`, `Worker`, `Code`, `Gate` e `Human`;
- arestas `dependency`, `correction`, `learning` e `approval`;
- condições por status, existência e igualdade usando JSON Pointer;
- cálculo de `ready_nodes` e despacho paralelo por ondas;
- retries configuráveis com evidências estruturadas por tentativa;
- gates determinísticos para exit code, JSON Schema básico, testes e aprovação
  humana;
- aprendizado de restrições após a sequência falha, correção e sucesso;
- identificação das camadas `Data`, `Knowledge` e `Execution`;
- executores desacoplados por meio do trait `NodeExecutor`;
- APIs `put_execution_graph`, `get_execution_graph`,
  `run_execution_graph` e `approve_execution_node` na fachada `NexusDB`.

Chamadas de LLM e execução de scripts não são habilitadas implicitamente. Cada
integração precisa registrar um adaptador em `ExecutorRegistry`. Consulte
`Docs/EXECUTION_GRAPHS.md` para o modelo e os limites atuais.

## Tests

```powershell
cargo test --all-targets
cargo clippy --all-targets
```

A suíte funcional HA e os testes dos grafos executáveis ficam no projeto
`test_funcoes_rust`:

```powershell
$env:NEXUSDB_TEST_ADMIN_PASSWORD = "senha-administrativa-do-cluster"
cargo run --offline --manifest-path test_funcoes_rust/Cargo.toml --bin test_ha_v22
```

Para executar apenas a suíte local do motor, sem depender de um cluster ativo:

```powershell
cargo test --offline --manifest-path test_funcoes_rust/Cargo.toml --bin test_ha_v22
```

## Windows helper scripts

Os scripts da raiz usam o próprio diretório do repositório e aceitam os perfis
`debug` e `release`:

```powershell
.\build_once_windows.bat debug
.\build_once_windows.bat release
```

No primeiro start, defina uma senha administrativa. Em HA, os três terminais
também devem receber exatamente o mesmo segredo de cluster, com pelo menos 32
caracteres. Não grave esses valores nos arquivos `.conf`:

```powershell
$env:NEXUSDB_ADMIN_PASSWORD = "replace-with-a-long-unique-password"
$env:NEXUSDB_HA_SECRET = "replace-with-at-least-32-random-characters"
```

Para garantir que os três processos herdem exatamente o mesmo segredo, inicie
o cluster inteiro pelo mesmo terminal:

```bat
set "NEXUSDB_ADMIN_PASSWORD=replace-with-a-long-unique-password"
set "NEXUSDB_HA_SECRET=replace-with-at-least-32-random-characters"
run_cluster_ha.bat
```

Também é possível iniciar `run_node1_ha.bat`, `run_node2_ha.bat` e
`run_node3_ha.bat` separadamente, desde que todos recebam o mesmo segredo. Para
reiniciar somente o primeiro membro após uma queda, execute `run_node1_ha.bat`;
o catch-up ocorre antes de ele voltar a atender. Para execução sem cluster, use
`run_node1_single_for_load.bat`. O modo de desempenho usa release por padrão e
pode ser iniciado com `run_node1_performance_mode.bat`.

Em modo console, encerre com `Ctrl+C` na janela do processo. O script
`kill_nexusdb_windows.bat` tenta parar o Windows Service de forma graciosa e só
usa `taskkill /F` quando chamado explicitamente com `--force`.

## Windows Service

Build the release binary and open an elevated PowerShell:

```powershell
cargo build --release
.\target\release\nexusdb.exe service install
notepad C:\ProgramData\NexusDB\config\nexusdb.env
.\target\release\nexusdb.exe service start
.\target\release\nexusdb.exe service status
```

The installer copies the binary to
`C:\Program Files\NexusDB\bin\nexusdb.exe`, creates protected configuration,
data, and log directories under `C:\ProgramData\NexusDB`, registers delayed
automatic startup, and configures restart after a process crash. The service
runs as the restricted built-in `LocalService` account. Its configuration is
read-only to that account; write access is limited to data, backups, and logs.

Before the first start, set a unique `NEXUSDB_ADMIN_PASSWORD` in
`C:\ProgramData\NexusDB\config\nexusdb.env`. After the first successful start,
remove that line because the Argon2id hash is already stored in the persistent
configuration database.

Management commands (run elevated when Windows requires it):

```powershell
nexusdb.exe service start
nexusdb.exe service stop
nexusdb.exe service restart
nexusdb.exe service status
nexusdb.exe service uninstall
```

Stopping the service uses the same graceful shutdown path as `Ctrl+C`.
Uninstalling preserves the configuration, database, and logs in `ProgramData`.

## Instalador Windows com Inno Setup

O projeto inclui `installer/nexusdb.iss`, que gera um instalador x64 por
máquina. Ele instala o binário release e a documentação, registra o Windows
Service sob `LocalService`, solicita a senha administrativa inicial em campo
oculto e mantém a escuta restrita a `127.0.0.1:7474` por padrão.

Com Rust, Inno Setup 6 ou 7, CUDA Toolkit (`nvcc` no PATH) e Visual Studio C++
Build Tools instalados, gere o pacote com:

```bat
build_installer_windows.bat
```

O pacote 0.1.1 inclui `nexusdb.exe` compilado com `--features cuda`,
`nexusdb_cuda.dll`, documentacao e exemplo de configuracao de compute.
Novas instalacoes usam `AUTO`; atualizacoes preservam a configuracao existente.
O resultado é gravado em `installer/output`. Atualizações param e reiniciam o
serviço de forma graciosa. A desinstalação remove o serviço e os arquivos do
programa, mas preserva configuração, bancos, backups e logs em
`C:\ProgramData\NexusDB`. Consulte `installer/README.md` para detalhes.

## Online password changes

Passwords can be changed while NexusDB is serving requests; no service restart
or database shutdown is needed. The new credential becomes effective on the
next request and the previous credential is rejected immediately.

- A user changes their own password with `POST /db/auth/password/change`, using
  the current `X-User` and `X-Pass` headers and the JSON body
  `{"new_password":"..."}`. This route also works when the current password is
  expired. A locked account must be reset by an administrator.
- An administrator resets any active user's password with
  `POST /db/admin/password/reset` and the JSON body
  `{"username":"...","new_password":"..."}`. The legacy path
  `/db/admin/password/change` remains available.

Both operations require at least 12 characters, reject reuse of the current
password, reset failed-login counters after success, and record an audit event
without recording password values. In HA laboratory mode, authentication data
is local to each node and is not replicated by the experimental data protocol;
perform the rotation independently on every node.

## Repository hygiene

Runtime databases, datasets, generated pages, archives, and third-party binary
documents are intentionally ignored. Publish only material whose license and
origin are known.

## License

MIT. See [LICENSE](LICENSE).


### Correção de DROP DATABASE / dropdb

A exclusão administrativa (`POST /db/admin/database/drop`) e `DROP DATABASE`
compartilham a limpeza do armazenamento, do proprietário e das permissões
específicas do banco. É possível recriar o mesmo nome sem herdar os grants
anteriores. O nome é resolvido sem distinção de maiúsculas/minúsculas entre
os bancos carregados; databases reservados continuam protegidos.

O catálogo é atualizado em uma transação SQLite. Se a remoção física falhar,
as alterações do catálogo são revertidas e o banco permanece registrado em
memória. Arquivos e catálogo não constituem uma transação atômica conjunta;
se a confirmação do catálogo falhar após remover os arquivos, repita a
exclusão administrativa para concluir a limpeza antes de recriar o banco.
Para instalações afetadas por metadados antigos, repita `dropdb` antes do
`CREATE DATABASE`, usando o servidor atualizado.

Regressão isolada: `cargo test --test database_lifecycle` (criação, exclusão
HTTP e SQL, recriação, limpeza de proprietário/grants e proteção de system).

## Projeções temporais e multicamadas

Visões por instante ou janela, camada e propriedades podem ser combinadas em
`CALL graph.project`, `CALL graph.projectDegree` e `CALL graph.projectPageRank`.
Os relacionamentos usam intervalos explícitos nas propriedades. Consulte
[semântica, exemplos e limitações](Docs/TEMPORAL_PROJECTIONS.md).

O [motor temporal](Docs/TEMPORAL_ENGINE.md) oferece histórico automático de
alterações e exclusões habilitado por database com `"temporal_history":true`
na API administrativa de criação/configuração, caminhos cronológicos,
recuperação GraphRAG por instante e snapshots CSR paginados em disco.
Execute o [hospital simulado](examples/README_TEMPORAL_DEMO.md) para validar
as funções em um diretório novo, isolado dos bancos existentes.

O [backend particionado](Docs/PARTITIONED_STORAGE.md) adiciona importação JSONL,
construção e BFS com memória limitada, propriedades sob demanda, checkpoints
e Arrow IPC com cliente Python e download autenticado. A ferramenta offline
é nexusdb-disk; bancos nesse modo não carregam o grafo no startup.
Consulte o [contrato openCypher](Docs/OPENCYPHER_COMPATIBILITY.md) para
parâmetros, CALL/YIELD/RETURN, atualizações de nós e SpMV.

Veja a [auditoria da gramática/TCK fornecidos](Docs/TCK_M23_AUDIT.md), com
limites e justificativas, e a [demonstração Python de grafos temporais](examples/README_TEMPORAL_PYTHON.md),
que gera dados simulados, relatório e uma linha do tempo interativa em HTML.

O [laboratório Python de mercados temporais](examples/README_CRYPTO_TEMPORAL_LAB.md)
abre uma interface Tkinter com redes multicamada, concentração, sincronismo,
evidências e cenários de controle. Usa apenas Python padrão e NexusDB, com
dados simulados ou CSV normalizado, sem afirmar causalidade de um colapso.

A [integração espacial](Docs/SPATIAL_INTEGRATION.md) oferece GeoJSON,
distâncias geográficas, projeções e caminho mínimo nativos, conversor
GeoParquet opcional e demonstração Python/Tkinter.

O [núcleo de conhecimento e deliberação](Docs/KNOWLEDGE_PHRONESIS.md) integra
memória histórica, BM25, recuperação híbrida, PPR, evidências, grounded,
MCDA e decisões auditáveis, com features opcionais. Execute a
[demonstração Python](examples/README_KNOWLEDGE_PHRONESIS.md) para testar
as funções no servidor isolado. A documentação distingue o suporte
implementado dos itens ainda pendentes dos roteiros Cortex/Phronesis.


O [gateway REST Rust/Axum](crates/nexusdb-rest-gateway/README.md) publica
operações de leitura com database e propriedades definidos, X-API-Key/Bearer,
chaves com duração e bloqueio por endpoint/database. O adaptador traduz as
rotas reais do NexusDB e preserva a execução dos algoritmos no servidor.
Execute [a validação Python com servidores reais](examples/rest_gateway_validation.py).

A [v0.3 do gateway](Docs/REST_GATEWAY_V03.md) acrescenta OpenAPI com acesso
controlado, auditoria, limites por database e cancelamento cooperativo no runtime,
além de relatórios por verificação e [benchmark CPU/GPU](examples/rest_gateway_benchmark.py).

O [MCP nativo v0.1](Docs/NATIVE_MCP.md), habilitado por opção, oferece descoberta e
execução de ferramentas de leitura dentro do processo Rust, com RBAC, sessões,
catálogo por database/usuário e cancelamento. Experimente o
[hospital sintético em Python](examples/native_mcp_demo.py) sem alterar o serviço instalado.

Documentação de [segurança de senhas, recuperação e cofres DPAPI](Docs/PASSWORD_SECURITY.md).
