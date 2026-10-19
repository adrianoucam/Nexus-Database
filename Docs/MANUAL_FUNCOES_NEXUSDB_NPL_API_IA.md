# Manual técnico das funções e operações — NexusDB, NPL/pg, API e IA

**Edição:** 1.0 · **Base documental:** exemplos e relatórios enviados em 18/10/2026 · **Idioma:** português (Brasil)

> **Escopo e evidência.** Este manual documenta as funções, comandos, procedimentos, endpoints e contratos **efetivamente utilizados** em `01_chaves_api.py`, `02_npl_academico.py`, `03_ia_graphrag.py`, `04_conhecimento_api.py`, `cliente_chave.py`, `common.py`, `executar_todos.py`, `local_gguf.py`, `test_local_gguf.py`, `perfil_academico.example.json`, `suite.json`, `report(2).json`, README e VALIDACAO. Exemplos adicionais abaixo são explicativos, não testes novos. Os arquivos descrevem 60 verificações aprovadas (26 de chaves, 16 de NPL, 9 de GraphRAG e 9 de conhecimento). A geração por LLM é opcional e **não foi executada** nessa validação.

## Índice

1. [Arquitetura e requisitos](#1-arquitetura-e-requisitos)
2. [Referência NPL/pg](#2-referência-nplpg)
3. [Cypher e procedimentos nativos](#3-cypher-e-procedimentos-nativos)
4. [API HTTP nativa](#4-api-http-nativa)
5. [Gateway e chaves de API](#5-gateway-e-chaves-de-api)
6. [Funções da biblioteca de laboratório Python](#6-funções-da-biblioteca-de-laboratório-python)
7. [Funções de GraphRAG e IA](#7-funções-de-graphrag-e-ia)
8. [Quatro exemplos completos](#8-quatro-exemplos-completos)
9. [Testes, erros e segurança](#9-testes-erros-e-segurança)
10. [Execução, limites e matriz de suporte](#10-execução-limites-e-matriz-de-suporte)

## 1. Arquitetura e requisitos

Há **duas interfaces de autenticação distintas**:

| Camada | Interface | Credenciais | Finalidade |
|---|---|---|---|
| NexusDB nativo | `/db/data/...`, `/db/npl` | `X-User`, `X-Pass`, `X-Database` | Consultas, administração, rotinas NPL e procedimentos nativos |
| Gateway REST | `/v1/endpoints/{id}` | `X-API-Key` ou `Authorization: Bearer` | Publicar somente operações, campos e parâmetros aprovados |
| Administração do gateway | `/admin/...` | `X-Gateway-Admin-Key` | Emitir/revogar chaves e controlar publicação |

**Uma chave do gateway não autentica diretamente no NexusDB nativo nem em `/db/npl`.** O gateway executa perfis previamente definidos com uma conta de serviço sujeita ao RBAC do banco.

### Compilação e execução

Requisitos declarados: Python 3.10+, binários compilados do NexusDB e do gateway; Ollama ou `llama-cpp-python` apenas para geração opcional.

```powershell
Set-Location E:\nexusdb
cargo build --features phronesis,datalog,embedded,spatial-geoparquet --bin nexusdb
cargo build --manifest-path crates/nexusdb-rest-gateway/Cargo.toml
python examples/academico_api_ia-Example/executar_todos.py
```

As features extras são necessárias ao exemplo de conhecimento (`04`). Cada laboratório cria processo, porta, banco e credenciais temporários, preservando relatórios e dados de demonstração em `target/academico-api-ia`.

## 2. Referência NPL/pg

O laboratório usa um **subconjunto procedural**, não PL/pgSQL integral.

### 2.1 `CREATE FUNCTION ... RETURNS ... BEGIN ... END;`

**Função:** definir uma rotina nomeada, com parâmetros e tipo de retorno. O registro é feito pela operação HTTP `register`.

```sql
CREATE FUNCTION situacao(nota FLOAT, frequencia FLOAT) RETURNS TEXT BEGIN
  IF frequencia < 75 THEN RETURN 'REPROVADO_FREQUENCIA'; END IF;
  IF nota >= 7 THEN RETURN 'APROVADO'; END IF;
  IF nota >= 5 THEN RETURN 'RECUPERACAO'; END IF;
  RETURN 'REPROVADO_NOTA';
END;
```

| Elemento | Significado | Demonstração |
|---|---|---|
| `CREATE FUNCTION` | Define a rotina | `situacao`, `materiais` |
| `FLOAT` | Tipo numérico dos argumentos | `nota`, `frequencia` |
| `TEXT` | Tipo textual | Retorno e argumento `curso` |
| `RETURNS TEXT` | Tipo de retorno | Classificação e JSON serializado |
| `BEGIN ... END` | Corpo da rotina | Agrupamento das instruções |
| `IF ... THEN ... END IF` | Condição | Prioridade da frequência |
| `RETURN` | Encerra a execução com valor | `APROVADO` |
| `DECLARE nome TEXT` | Variável local | `resultado` |

As comparações `<` e `>=` são empregadas na rotina de classificação. Os limites de 75%, 7 e 5 são **fictícios**, para ensino.

### 2.2 `CALL` — invocar uma rotina

```json
{"operation":"call","query":"CALL situacao(8, 90);"}
```

Enviado por `POST /db/npl`, retorna no laboratório um envelope com `resultados[0].value`. Exemplos observados:

| Chamada | Resultado |
|---|---|
| `CALL situacao(8, 90);` | `APROVADO` |
| `CALL situacao(6, 90);` | `RECUPERACAO` |
| `CALL situacao(4, 90);` | `REPROVADO_NOTA` |
| `CALL situacao(10, 74);` | `REPROVADO_FREQUENCIA` |
| `CALL situacao(7, 75);` | `APROVADO` |

O registro e a chamada são restritos por autenticação, autorização e propriedade da rotina; o usuário de leitura do teste não pode registrar nem chamar rotina pertencente a outro proprietário.

### 2.3 `EXECUTE CYPHER ... USING ... INTO ...`

Executa uma consulta de leitura com parâmetros tipados e armazena o resultado em uma variável NPL:

```sql
CREATE FUNCTION materiais(curso TEXT) RETURNS TEXT BEGIN
  DECLARE resultado TEXT;
  EXECUTE CYPHER 'MATCH (n:Material) WHERE n.curso = $curso RETURN n LIMIT 10'
    USING curso := curso INTO resultado;
  RETURN resultado;
END;
```

| Parte | Papel |
|---|---|
| `MATCH (n:Material)` | Seleciona nós com rótulo `Material` |
| `WHERE n.curso = $curso` | Filtra usando parâmetro nomeado |
| `RETURN n` | Devolve os nós |
| `LIMIT 10` | Limita a consulta |
| `USING curso := curso` | Vincula o parâmetro Cypher à variável NPL |
| `INTO resultado` | Recebe a resposta textual |

O cliente do exemplo interpreta o retorno como JSON via `json.loads` e verifica `processados == 1`. **Não inferir suporte a Cypher arbitrário ou escrita dentro de NPL** a partir desse caso.

### 2.4 Operações da API NPL

| `operation` | Entrada | Resultado/controle |
|---|---|---|
| `register` | `name`, `source` | Registra a rotina; o teste espera `version == 1` |
| `call` | `query` contendo `CALL ...;` | Executa rotina autorizada |
| `memory_stats` | Sem argumentos no exemplo | Estatísticas administrativas de reservas de memória |
| `begin` | — | **Recusada (HTTP 400)** neste laboratório |
| `commit` | — | **Recusada (HTTP 400)** |
| `rollback` | — | **Recusada (HTTP 400)** |
| `write_cypher` | — | **Recusada (HTTP 400)** |

`memory_stats` requer privilégio ADMIN; o teste verifica `active_reservations == 0` após a execução. A métrica é de **reservas estimadas da NPL**, não medição integral de RSS, VRAM ou garantia de limite físico.

## 3. Cypher e procedimentos nativos

As chamadas a seguir ocorrem via `/db/data/cypher` e **não** devem ser confundidas com rotinas NPL, embora ambas usem a palavra `CALL`.

### 3.1 `MATCH`, `WHERE`, `RETURN`, `LIMIT`

```cypher
MATCH (n:Material) WHERE n.curso=$curso RETURN n
```

Usado no perfil `consulta` do gateway. A coluna pública `titulo` é projetada de `/n/properties/titulo`. O parâmetro é validado pelo gateway; o teste registra que um literal malicioso com aspas e `DELETE` é recusado pelo parser desta versão, com erro específico `NEXUSDB_PROCEDURE_REJECTED` (HTTP 502), e os três materiais permanecem no banco. Isso **não equivale** a provar segurança contra toda classe de injeção.

### 3.2 `CALL vector.createIndex(...)`

```cypher
CALL vector.createIndex('academico','Evidencia','embedding',3,'cosine')
```

Cria índice vetorial para o conjunto demonstrado, com dimensão 3 e métrica cosseno. Os vetores usados são sintéticos, não embeddings semânticos reais.

### 3.3 `CALL graphRAG.retrieve(...)`

```cypher
CALL graphRAG.retrieve('academico',[1,0,0],1,64,3,10)
```

Recupera nós e contexto relacionados ao vetor e grafo segundo a assinatura posicional usada no exemplo. O teste confere os nós de documento, projeto, laboratório e equipamento, além de `truncated == false`. **O material não fornece contrato formal de cada posição**, portanto não se deve atribuir nomes definitivos aos seis argumentos sem consultar a implementação do procedimento. Essa chamada usa credenciais nativas do operador; não foi publicada na allowlist do gateway.

### 3.4 `CALL knowledge.initialize`

```python
lab.session.call('knowledge.initialize', {})
```

Inicializa o subsistema de conhecimento no banco isolado do exemplo 04. Executado antes da gravação de memórias.

### 3.5 `CALL memory.remember($request)`

```json
{
  "content": "Projeto P001 utiliza laboratório L001.",
  "origin": {"kind": "document", "id": "ACADEMIC-SYNTHETIC", "version": "v1"},
  "valid_from": 0,
  "embedding": {"model_id": "SYNTHETIC-3D", "values": [1.0, 0.0, 0.0]}
}
```

O exemplo passa esse objeto como parâmetro `request` de `CALL memory.remember($request)` e lê `statement_results[0].node_id`. Cria três memórias da conta de leitura e uma memória privada do administrador. A autorização é aplicada à recuperação.

### 3.6 `knowledge.hybridSearch`

Publicado no gateway por um perfil `kind: call`, com `procedure: knowledge.hybridSearch`. Os argumentos do perfil são **fixados pelo operador**:

```json
{
  "query": "Projeto",
  "embedding": {"model_id": "SYNTHETIC-3D", "values": [1,0,0]},
  "seeds": [1]
}
```

`seeds: [1]` é **ilustrativo**; o código usa o ID efetivamente retornado pela gravação. A resposta projetada possui `id`, `excerpt` e `contributions`, onde foram observados os componentes `lexical`, `vector_exact` e `graph_ppr` (Personalized PageRank). São contribuições de ranking, **não probabilidades de veracidade**.

### 3.7 `knowledge.contextPack`

Perfil de procedimento com `query: "Projeto"`, `max_chars: 1000`. Publica `id`, `excerpt`, `origin` e preserva a proveniência documental. É útil para montar contexto de resposta sem liberar todo o registro.

### 3.8 `knowledge.search`

O perfil `sem-evidencia` executa uma busca com termo artificial inexistente e espera `rows: []`. O texto didático `Evidência insuficiente.` é produzido pelo exemplo; **não é uma resposta gerada automaticamente por LLM**.

### 3.9 Comandos de autorização

```cypher
REVOKE READ ON DATABASE EXAMPLE_ACADEMICO_CHAVES FROM academic_reader
REVOKE WRITE ON DATABASE EXAMPLE_ACADEMICO_CONHECIMENTO FROM academic_reader
```

O primeiro testa que uma API key válida não supera a revogação READ no banco. O segundo retira WRITE depois de popular o laboratório de conhecimento. Os nomes de banco refletem os ambientes isolados dos exemplos; não execute essas revogações em bancos de produção sem planejamento.

## 4. API HTTP nativa

| Método e rota | Finalidade | Corpo representativo |
|---|---|---|
| `POST /db/npl` | Registrar/chamar rotina, obter memória | `{"operation":"memory_stats"}` |
| `POST /db/data/cypher` | Consultar/procedimento Cypher | `{"statements":[{"query":"CALL ..."}]}` |
| `POST /db/data/node/bulk` | Inserir nós de laboratório | `{"rows":[{"key":"a","label":"Material","properties":{}}]}` |
| `POST /db/data/relationship/bulk` | Inserir arestas | `{"rows":[{"key":"r","from":1,"to":2,"type":"RELACIONADO","properties":{}}]}` |
| `POST /db/admin/user/create` | Criar usuário de teste | `username`, `password`, `role`, `expires_days` |
| `POST /db/admin/grant` | Conceder acesso | `username`, `database`, `access` (`READ`/`WRITE`) |

Em `/db/data/cypher`, `include_statement_results: true` é usado no laboratório 04 para recuperar `node_id`. O helper `Lab.seed()` verifica se o número de nós/arestas persistidos coincide com o solicitado.

### Formato de nós e relacionamentos

```json
{
  "rows": [
    {"key":"doc", "label":"Evidencia", "properties":{"tipo":"Documento","publicado":true}}
  ]
}
```

Arestas usam IDs numéricos **retornados pela inserção**, não IDs presumidos. Os campos `key` nos lotes permitem relacionar entradas locais aos IDs criados.

## 5. Gateway e chaves de API

### 5.1 Definição de perfil `lab.endpoint(...)`

```json
{
  "database":"EXAMPLE_ACADEMICO_PUBLICADO",
  "user_env":"ACADEMIC_READER",
  "password_env":"ACADEMIC_PASSWORD",
  "max_rows":20,
  "params":{"curso":{"kind":"string","required":true,"values":["Computacao","Administracao"]}},
  "operation":{"kind":"nodes","label":"Material","properties":["titulo","curso"],"filters":{"publicado":true},"filter_params":{"curso":"curso"}}
}
```

`user_env` e `password_env` apontam para variáveis privadas no **processo gateway**, não para valores expostos ao consumidor. `max_rows` limita resultados publicados. O filtro `publicado: true` é fixo pelo operador.

### 5.2 Tipos de operação `kind`

| Tipo | Campos usados | Papel |
|---|---|---|
| `nodes` | `label`, `properties`, `filters`, `filter_params` | Publica nós e apenas propriedades autorizadas |
| `relationships` | `relationship_type`, `properties` | Publica relações autorizadas; perfil usa parâmetro `from` |
| `query` | `query`, `columns` | Executa consulta Cypher previamente salva |
| `call` | `procedure`, `args`, `columns` | Invoca procedimento nativo permitido pelo gateway |

`columns` é um mapa de nome público para caminho no resultado, como `"excerpt": "/excerpt"`. Um consumidor **não pode substituir a consulta publicada** nem inserir parâmetros não previstos no contrato.

### 5.3 Administração e consumo

| Método e rota | Autorização | Função |
|---|---|---|
| `POST /admin/endpoints/{endpoint}/keys` | Chave administrativa | Emite chave com `ttl_seconds`; retorna `api_key`, `key_id`, `expires_at_ms` |
| `POST /admin/access` | Chave administrativa | Ativa/desativa `key`, `endpoint`, `database` ou `global` |
| `GET /admin/state` | Chave administrativa | Inspeciona estado sem expor segredos |
| `POST /v1/endpoints/{endpoint}` | Chave de dados do endpoint | Executa perfil com `{"params":{...}}` |

Exemplo de consumo com PowerShell (pressupõe chave emitida legitimamente):

```powershell
$headers = @{ 'X-API-Key' = $env:NEXUSDB_API_KEY }
Invoke-RestMethod -Method Post `
  -Uri 'http://127.0.0.1:8787/v1/endpoints/materiais' `
  -Headers $headers -ContentType 'application/json' `
  -Body '{"params":{"curso":"Computacao"}}'
```

Para revogar:

```powershell
$body = @{ scope='key'; id=$keyId; enabled=$false } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8787/admin/access' `
  -Headers @{ 'X-Gateway-Admin-Key' = $env:NEXUSDB_GATEWAY_ADMIN_KEY } `
  -ContentType 'application/json' -Body $body
```

O teste cobre validade temporal, revogação individual, reativação, bloqueio de endpoint, banco e global. A chave não deve aparecer em linha de comando, logs ou relatórios compartilhados. Em rede remota, usar HTTPS.

## 6. Funções da biblioteca de laboratório Python

### 6.1 `options(description)`

Cria o parser de linha de comando comum aos quatro exemplos. Argumentos: `--server`, `--gateway`, `--output`, `--ollama-model`, `--gguf`, `--gguf-python`, `--llm-context` (4096 padrão) e `--llm-max-tokens` (384 padrão). `--gguf` e `--ollama-model` são mutuamente exclusivos.

### 6.2 `Lab(args, name)` e ciclo de vida

`Lab` é um gerenciador de contexto (`with Lab(...) as lab`) que cria diretório isolado, banco `EXAMPLE_ACADEMICO_{NOME}`, credenciais aleatórias, sessão nativa, conta `academic_reader` e concessão READ. No encerramento, finaliza apenas processos iniciados pelo laboratório e salva relatório.

| Método | Assinatura usada | Comportamento |
|---|---|---|
| `save()` | `lab.save()` | Grava `report.json` com checks, evidências e limitações |
| `check(name, condition)` | `lab.check('...', status == 200)` | Registra verificação; lança `AssertionError` se falhar |
| `endpoint(operation, **extra)` | `lab.endpoint({...}, params={...})` | Monta perfil publicado com banco, conta e `max_rows` |
| `start_gateway(endpoints)` | `lab.start_gateway({'materiais': perfil})` | Grava `endpoints.json`, inicia gateway local em porta livre |
| `stop_gateway()` | `lab.stop_gateway()` | Encerra processo do gateway iniciado pelo laboratório |
| `request(path, payload, *, key, admin, bearer, native)` | `lab.request('/admin/state', admin=True)` | Requisição HTTP e retorno `(status, json)`; registra `http_trace` |
| `issue(endpoint, ttl=3600, **extra)` | `lab.issue('materiais', ttl=1)` | Emite e guarda chave em memória |
| `call(endpoint, params=None, **extra)` | `lab.call('materiais', {'curso':'Computacao'})` | Chama endpoint com a chave correspondente |
| `toggle(scope, identity, enabled)` | `lab.toggle('endpoint','busca',False)` | Bloqueia ou libera escopo no gateway |
| `cypher(query)` | `lab.cypher('CALL ...')` | Envia consulta à API Cypher nativa |
| `seed(nodes, edges=())` | `ids = lab.seed([...], [...])` | Insere nós/arestas e devolve mapa `key → id` |

**Observação:** `request(..., native=True)` envia ao endereço da sessão NexusDB; o padrão usa o gateway. O método de `urllib.request.Request` é POST quando há corpo JSON, GET quando não há corpo, conforme comportamento da biblioteca Python.

### 6.3 `NexusSession` (dependência externa aos arquivos fornecidos)

A classe é importada de `crypto_temporal_lab` e oferece, nos exemplos, `request(path, payload, user=..., password=...)`, `call(procedure, args)` e `close()`, além de `url`. Sua implementação **não foi enviada**; não se documentam outras assinaturas ou garantias além dessas chamadas observadas.

### 6.4 `main()` dos programas

`main()` em cada `01`–`04` orquestra um laboratório; `main()` de `cliente_chave.py` consome um endpoint existente; `main()` de `executar_todos.py` roda os quatro programas em subprocessos separados, grava `suite.json` e devolve código de saída 0 somente quando todos terminam com sucesso.

### 6.5 `cliente_chave.py`

Usa `GatewayTransport(url, {endpoint: token}).call(endpoint, params)`; obtém a chave de `NEXUSDB_API_KEY`, o endereço de `NEXUSDB_GATEWAY_URL` e valida que `--params` seja um objeto JSON. Não recebe segredo por argumento de processo.

```powershell
$env:NEXUSDB_GATEWAY_URL='http://127.0.0.1:8787'
# NEXUSDB_API_KEY deve ter sido carregada de fonte privada.
python cliente_chave.py --endpoint materiais --params '{"curso":"Computacao"}'
```

## 7. Funções de GraphRAG e IA

### 7.1 `cosine(a, b)`

Importada de `nexusdb_ai.core`; aplicada a vetores sintéticos de três dimensões para ordenar documentos por similaridade. O código dessa função **não foi anexado**, portanto o manual não atribui implementação específica de normalização ou tratamento de vetores nulos.

### 7.2 `GatewayTransport` e `PublishedGatewayAdapter`

Importados de `nexusdb_ai.gateway_adapter` (implementação não anexada). O uso observado é:

```python
adapter = PublishedGatewayAdapter(
    GatewayTransport(lab.url, lab.keys),
    'evidencias', 'vinculos'
)
public_nodes = adapter.nodes()
links = adapter.neighbors(node_id, 'RELACIONADO')
```

`nodes()` retorna nós publicados; `neighbors()` retorna vizinhos na fatia autorizada. O teste confirma que uma relação para nó privado não permite acessar o nó privado.

### 7.3 `expand(adapter, seed, max_depth=3, max_nodes=10)`

Função **definida no arquivo `03_ia_graphrag.py`**. Realiza expansão em largura (*breadth-first search*, BFS) usando `collections.deque`, controla nós visitados (`seen`) e retorna evidências com `id`, `depth` e `properties`. Expande relações `RELACIONADO` até `max_depth`; se atingir o limite de nós, lança erro para evitar resposta parcial silenciosa.

```python
context = expand(adapter, ranked[0], max_depth=3, max_nodes=10)
```

A expansão ocorre no **cliente Python** sobre dados publicados pelo gateway; não é a mesma execução do `graphRAG.retrieve` nativo.

### 7.4 `Ollama(model=...).generate(prompt)`

Cliente importado de `nexusdb_ai.core`, usado somente se `--ollama-model` for informado. O exemplo orienta a LLM a responder com base nas evidências, citar IDs e não inventar causas. A implementação do cliente Ollama não foi fornecida.

### 7.5 `local_gguf.generate(path, prompt, context=4096, max_tokens=384)`

Carrega modelo GGUF via `llama_cpp.Llama` com `n_ctx=context`, `n_gpu_layers=0` (**CPU**), `verbose=False`; usa `create_chat_completion(messages=[{'role':'user','content':prompt}], temperature=0, max_tokens=max_tokens, stream=False)` e encerra o modelo em `finally: model.close()`.

Retorna `(texto, metadata)` com modo, modelo, backend solicitado, duração de carregamento/geração, tokens e motivo de término. `finish_reason='length'` indica possível interrupção por limite.

### 7.6 `local_gguf.generate_external(python, path, prompt, context=4096, max_tokens=384)`

Executa `local_gguf.py` em subprocesso Python separado, enviando solicitação JSON por stdin. Constrói ambiente com lista explícita de variáveis permitidas; **não repassa `NEXUSDB_PASSWORD` nem `NEXUSDB_API_KEY`**. Captura saída, aplica timeout de 1800 segundos e rejeita execução com código diferente de zero. O teste unitário cobre isolamento de credenciais e falha do worker.

```powershell
python 03_ia_graphrag.py `
  --gguf 'F:\Jarvis\modelos_locais\gemma-3-1b-it-Q4_K_M.gguf' `
  --gguf-python 'F:\WinPython\python\python.exe'
```

Esses caminhos constam do README fornecido como exemplo de ambiente, **não são requisitos universais**. O modelo GGUF deve existir localmente e ser compatível com o `llama-cpp-python` instalado.

### 7.7 Resposta determinística versus geração

Sem `--gguf` ou `--ollama-model`, o exemplo 03 produz uma resposta textual por template, registra `generation.mode='deterministic_template'` e `llm_executed=false`. Com LLM, registra `review_required=true` e `factual_accuracy_validated=false`. A presença de resposta textual não comprova sua precisão factual.

## 8. Quatro exemplos completos

### Exemplo 01 — Chaves e publicação de biblioteca

**Dados:** três materiais, incluindo `titulo`, `curso`, `publicado` e anotação interna. **Perfis:** `materiais`, `todos`, `curto`, `consulta`. **Funções exercitadas:** `seed`, `endpoint`, `start_gateway`, `issue`, `call`, `request`, `toggle`, `cypher`. **Resultados esperados:** campos privados omitidos, filtros validados, limite/truncamento visível, autenticação e revogação aplicadas. **Testes:** 26 aprovados no relatório de validação.

### Exemplo 02 — NPL acadêmica

**Dados:** dois materiais. **Rotinas:** `situacao` e `materiais`. **Operações:** `register`, `call`, `memory_stats`, `EXECUTE CYPHER ... USING ... INTO`. **Resultados esperados:** cinco classificações didáticas, leitura parametrizada, recusa de privilégios inadequados e recusa de transações/escritas indisponíveis. **Testes:** 16 aprovados.

### Exemplo 03 — IA/GraphRAG

**Dados:** seis nós e quatro relações; cinco nós publicados e um privado. **Funções:** `vector.createIndex`, `graphRAG.retrieve`, `cosine`, `GatewayTransport`, `PublishedGatewayAdapter`, `expand`; `Ollama.generate` ou `local_gguf.generate` somente se explicitamente selecionado. **Resultados esperados:** contexto contendo documento, projeto, laboratório e equipamento; conteúdo privado não publicado; expansão limitada. **Testes:** nove aprovados sem LLM.

### Exemplo 04 — Conhecimento híbrido

**Dados:** quatro memórias, uma privada, e uma relação `DEPENDE_DE`. **Procedimentos:** `knowledge.initialize`, `memory.remember`, `knowledge.hybridSearch`, `knowledge.contextPack`, `knowledge.search`. **Resultados esperados:** contribuição lexical, vetorial e de grafo, proveniência, ACL e revogação de endpoint. **Testes:** nove aprovados.

## 9. Testes, erros e segurança

### 9.1 Resultado dos arquivos enviados

| Laboratório | Verificações | Resultado registrado |
|---|---:|---|
| Chaves | 26 | Aprovado |
| NPL | 16 | Aprovado |
| GraphRAG | 9 | Aprovado |
| Conhecimento | 9 | Aprovado |
| **Total** | **60** | **Aprovado nos relatórios enviados** |

O `suite.json` registra saída zero para os quatro scripts. `report(2).json` detalha nove verificações do laboratório de conhecimento e inclui `http_trace`, resultados de busca e limitações. **Esses resultados foram produzidos no ambiente relatado pelos arquivos; este manual não representa uma nova execução da suíte.**

### 9.2 Casos de erro demonstrados

| Condição | Resposta verificada | Interpretação |
|---|---|---|
| Sem chave ou chave inválida | HTTP 401 | Falha de autenticação |
| Chave para endpoint diferente | HTTP 401 | Isolamento de perfil |
| Parâmetro ausente, inválido ou extra | HTTP 400 | Contrato rejeitado |
| Endpoint/banco/global desabilitado | HTTP 403 | Acesso bloqueado |
| `READ` revogado no NexusDB | HTTP 403 | RBAC nativo prevalece |
| Chave expirada | `API_KEY_EXPIRED` | Prazo excedido |
| Chave revogada | `API_KEY_REVOKED` | Credencial desativada |
| Literal rejeitado pelo parser Cypher | HTTP 502 / `NEXUSDB_PROCEDURE_REJECTED` | Recusa específica; estado persistido verificado |
| Operações NPL transacionais indisponíveis | HTTP 400 | Recurso não habilitado |
| Expansão de grafo acima de `max_nodes` | `RuntimeError` | Impede contexto parcial silencioso |
| Worker GGUF falha | `RuntimeError` | Falha não tratada como resposta gerada |

### 9.3 Testes do worker GGUF

`test_local_gguf.py` contém três testes `unittest`: não herdar segredos do banco, não aceitar falha do subprocesso como resposta e fechar o modelo após erro de geração. Esses testes usam *mocks*, **não carregam pesos nem executam inferência real**.

```powershell
python -m unittest test_local_gguf.py -v
```

### 9.4 Boas práticas ilustradas

- Publicar campos mínimos e filtros fixos; não entregar anotações internas.
- Restringir cada chave ao endpoint publicado; usar prazo de validade e revogação.
- Manter senha do banco no gateway, não no consumidor.
- Aplicar RBAC/ACL antes de recuperar dados para IA.
- Tratar documentos recuperados como dados não confiáveis, não instruções.
- Exigir proveniência e reconhecer ausência de evidência.
- Rejeitar contexto truncado quando isso comprometer a resposta.
- Não confundir erro HTTP, conjunto vazio e ausência real de registros.

## 10. Execução, limites e matriz de suporte

### 10.1 Comandos úteis

```powershell
# Todos os laboratórios
python executar_todos.py

# Isoladamente
python 01_chaves_api.py
python 02_npl_academico.py
python 03_ia_graphrag.py
python 04_conhecimento_api.py

# Cliente de chave previamente emitida
python cliente_chave.py --endpoint materiais --params '{"curso":"Computacao"}'

# Testes unitários do worker
python -m unittest test_local_gguf.py -v
```

Os scripts esperam ser executados dentro da estrutura de diretórios do repositório descrita no README: `common.py` importa `example_packages` e `crypto_temporal_lab`, e os módulos `nexusdb_ai` precisam estar acessíveis. Copiar somente os arquivos Python para uma pasta arbitrária **não basta** para executar a suíte.

### 10.2 Estado comprovado versus não demonstrado

| Capacidade | Evidência nos exemplos | Limitação |
|---|---|---|
| NPL: `CREATE FUNCTION`, `CALL`, condições | Testes HTTP reais relatados | Subconjunto da linguagem |
| NPL: `EXECUTE CYPHER` parametrizado | Leitura demonstrada | Não comprova escrita arbitrária |
| NPL: `memory_stats` | Reservas zeradas após execução | Não mede toda RAM/RSS |
| Gateway: API keys e RBAC | Testes de acesso e revogação | Não equivale a implantação TLS remota |
| Índice vetorial e GraphRAG nativos | Recuperação em grafo sintético | Sem benchmark de escala/qualidade semântica |
| Recuperação híbrida e ACL | Contribuições e privacidade verificadas | Scores não são probabilidades |
| LLM local GGUF/Ollama | Caminhos de código presentes | Inferência não executada na rodada relatada |
| Cache HOT/WARM/COLD | **Não exercitado nestes exemplos** | Integração automática não demonstrada |
| MVCC/ACID e transações NPL | **Não demonstrado** | `begin`, `commit`, `rollback`, `write_cypher` recusados |
| Snapshot transacional entre leituras do gateway | **Não demonstrado** | Leituras sucessivas podem observar versões distintas |

### 10.3 Glossário breve

**ACL:** regras de acesso aos dados. **API key:** segredo para consumir um perfil publicado. **RBAC:** autorização baseada em papéis/permissões. **NPL:** linguagem procedural do NexusDB demonstrada no exemplo. **Cypher:** linguagem de consulta de grafos. **RAG:** recuperação de informação para apoiar geração de respostas. **GraphRAG:** RAG enriquecido com relações de grafo. **PPR:** Personalized PageRank, sinal de relevância estrutural. **GGUF:** formato de arquivo para modelos locais. **HOT/WARM/COLD:** níveis de armazenamento/cache; não validados nesta suíte. **Proveniência:** origem rastreável de uma evidência.

---

## Fontes do manual

Arquivos fornecidos pelo usuário: `01_chaves_api.py`, `02_npl_academico.py`, `03_ia_graphrag.py`, `04_conhecimento_api.py`, `cliente_chave.py`, `common.py`, `executar_todos.py`, `local_gguf.py`, `test_local_gguf.py`, `perfil_academico.example.json`, `README(20261018-225019).md`, `VALIDACAO.md`, `suite.json`, `report(2).json`.

**Limite de documentação:** implementações importadas de `nexusdb_ai`, `crypto_temporal_lab` e do núcleo Rust não foram fornecidas neste conjunto. Este manual descreve somente as chamadas, parâmetros e efeitos observáveis nos arquivos, sem presumir contratos internos não apresentados.
