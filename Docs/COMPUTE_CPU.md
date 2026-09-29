# Compute: fases 1 a 4

Degree e PageRank nas rotas CALL existentes usam um pool Rayon compartilhado por
processo. CPU_SERIAL executa no chamador; CPU_PARALLEL usa o pool limitado.
AUTO escolhe por heuristicas e CUDA e opcional para PageRank. Nao ha modelo
aprendido nesta etapa. Os kernels CPU anteriores
continuam disponiveis como referencia atraves de GraphAlgorithm.

Variaveis no ambiente do servidor (ou nexusdb.env do servico):

| Variavel | Padrao | Significado |
|---|---|---|
| NEXUSDB_COMPUTE_BACKEND | AUTO | AUTO, CPU_SERIAL, CPU_PARALLEL ou CUDA |
| NEXUSDB_COMPUTE_THREADS | CPUs disponiveis | Tamanho do pool compartilhado |
| NEXUSDB_COMPUTE_MEMORY_MB | 256 | Orcamento agregado estimado de vetores de trabalho |
| NEXUSDB_COMPUTE_MAX_JOBS | 2 | Computacoes/resultados simultaneamente admitidos |
| NEXUSDB_COMPUTE_TIMEOUT_MS | 30000 | Prazo cooperativo da chamada |

Reinicie o processo apos alterar limites do pool. Em cluster, cada processo
tem seu proprio pool/orcamento; dimensione os limites somados dos nos.

### Secoes no arquivo do servico

O `nexusdb.env` do servico (ou arquivo passado a `run --config`) aceita,
ao final das variaveis dotenv existentes, estas secoes de estilo INI:

```ini
[compute]
backend = "AUTO"
threads = 12
memory_mb = 512
max_jobs = 2
timeout_ms = 300000

[compute.cuda]
enabled = true
# library = 'C:/Program Files/NexusDB/bin/nexusdb_cuda.dll'
```

Substitua as variaveis `NEXUSDB_COMPUTE_*` equivalentes pelas secoes; evite
definir a mesma opcao nas duas formas. As variaveis ja presentes no ambiente
do processo continuam tendo prioridade sobre o arquivo. Mantenha as demais
variaveis `NEXUSDB_*` antes das secoes. Este formato estende dotenv; nao e um
parser TOML geral. Numeros devem ser inteiros positivos, booleanos `true` ou
`false`; chaves desconhecidas e valores invalidos nas secoes impedem o start.

`enabled` equivale a `NEXUSDB_CUDA_ENABLED` (padrao `true`, preservando o
comportamento anterior). `false` impede a selecao CUDA: AUTO usa CPU e o backend
CUDA explicito retorna `CUDA_DISABLED`. `true` permite tentar CUDA, mas nao
compila nem instala o suporte. Ainda exige Windows 64 bits, executavel compilado
com `--features cuda`, DLL e driver compativeis. AUTO conserva suas heuristicas
e fallback; nao garante execucao na GPU. Reinicie o servico apos editar o arquivo.

O contrato Rust e ExecutionContext + CancellationToken. As funcoes
degree_with_context e page_rank_with_context aceitam backend e timeout explicitos.
Outro thread pode chamar token.cancel(). CALL utiliza o timeout configurado;
a desconexao HTTP ainda nao cancela automaticamente e nao ha endpoint remoto
de cancelamento nesta etapa.

Admissao e imediata: COMPUTE_BUSY quando falta uma vaga; COMPUTE_MEMORY_LIMIT
quando falta orcamento. A reserva de 64 bytes por vertice cobre uma estimativa
conservadora dos vetores numericos, coleta paralela e ordenacao. Fica retida
ate a liberacao do resultado computacional, inclusive na montagem da resposta.
Nao e um limite do RSS: nao inclui CSR/cache do storage, construcao do snapshot,
propriedades JSON, buffers HTTP ou alocacoes internas do sistema/Rayon.

O snapshot e obtido sob lock; os kernels e a ordenacao executam fora do lock.
Ao montar as propriedades dos nos selecionados, verifica-se a identidade do
snapshot. Alteracao ou expulsao da projecao causa COMPUTE_SNAPSHOT_CHANGED,
sem misturar scores antigos com propriedades novas. Repita a consulta nesse caso.
A construcao inicial do CSR e a copia final das propriedades ainda usam o lock.

Cancelamento e timeout sao cooperativos: verificacoes por vertice, a cada 4096
arestas de um vertice, nas iteracoes e entre etapas. Espera pelo lock, construcao
do snapshot, alocacoes e ordenacao nao possuem interrupcao imediata.

PageRank utiliza pull sobre reverse-CSR com reducao sequencial da massa dos
vertices sem saida. Cada vertice tem ordem de soma fixa entre os backends; a
comparacao com a implementacao anterior usa tolerancia numerica. Degree preserva
multiarestas e conta autoarestas uma vez. Nao foi prometido ganho sem benchmark.

## AUTO e telemetria

Heuristica v1 (limiares iniciais, nao calibrados por benchmark):

- CPU paralela quando ha mais de uma thread, pelo menos 2048 vertices e
  `(vertices + arestas) * max(iteracoes, 1) >= 100000`; caso contrario, serial.
- PageRank candidato a CUDA a partir de 100000 vertices, 1000000 arestas e
  10 iteracoes, se o modulo/dispositivo estiver disponivel e houver VRAM.
- CUDA explicito e estrito: erro se indisponivel ou sem VRAM; Degree CUDA
  retorna CUDA_UNSUPPORTED_OPERATION. AUTO registra a causa e volta a CPU.
- Falha CUDA durante a execucao em AUTO descarta resultados parciais e recomeca
  na CPU com o mesmo prazo e reserva. Timeout/cancelamento nao provoca retry.

Cada resposta Degree/PageRank inclui `execution`, com backend solicitado e
efetivo, motivo, fallback, vertices, arestas, iteracoes, reserva estimada e tempos
de snapshot, admissao, selecao, computacao, ordenacao, materializacao e total.
No endpoint `/db/data/cypher`, o campo superior `execution` e uma lista dos
relatorios das chamadas bem-sucedidas, na ordem das chamadas.
O campo `threads` informa a capacidade configurada do pool CPU, nao uma medicao
do numero de threads simultaneamente ocupadas pelo algoritmo.

O total mede a chamada no servidor ate a montagem do Value JSON; nao inclui
autenticacao, codificacao HTTP nem transporte de rede. CUDA informa separadamente
alocacao, upload, kernels/sincronizacao e download. Esses tempos sao wall-clock,
incluindo overhead/JIT quando aplicavel; nao sao medidas de pico de memoria.
`compute::telemetry::history()` fornece os ultimos 256 relatorios em memoria,
incluindo erros e cancelamentos. Nao persiste SQL, senhas ou propriedades.

## PageRank CUDA opcional (Windows x64)

Build completo pelo script: `build_once_windows.bat release cuda` compila a DLL
e o servidor com a feature CUDA em `target/release`. Para debug, use
`build_once_windows.bat debug cuda`. Sem o segundo argumento o build continua
CPU. O script em `src/` encaminha os mesmos argumentos ao script da raiz.

Compile o servidor com `cargo build --release --features cuda`. Em seguida,
execute `cuda\build_windows.bat`, com CUDA Toolkit (nvcc) no PATH e Visual Studio
C++ Build Tools instalado. O build gera `target/release/nexusdb_cuda.dll` com
runtime CUDA estatico e PTX para dispositivos compativeis com compute_75 ou
posterior. A JIT exige um driver compativel com a versao do Toolkit utilizada.
Mantenha a DLL junto ao executavel, ou configure NEXUSDB_CUDA_LIBRARY com caminho
absoluto confiavel. O processo carrega codigo nativo desse arquivo; proteja-o
contra escrita por usuarios nao administradores. A partir do pacote 0.1.1,
`build_installer_windows.bat` ativa a feature CUDA e inclui a DLL no instalador.
A resolucao da DLL e armazenada por processo, inclusive quando falha: reinicie
o servidor depois de instalar/substituir o modulo ou corrigir seu caminho.

O servidor sem a feature continua compilando e funcionando sem Toolkit, driver
ou GPU. Em outros sistemas, esta primeira versao retorna CUDA_NOT_BUILT e AUTO
usa CPU. A feature nao adiciona dependencia CUDA ao carregamento do executavel.

Usa dispositivo 0 e serializa trabalhos GPU por processo. CSR reverso, offsets
de saida e vetores de scores permanecem na GPU ate o final. Nao transfere pesos,
tipos ou IDs de arestas (PageRank atual e nao ponderado). Exige que todos os
buffers caibam em ate 80% da VRAM livre, deixando tambem pelo menos 256 MiB
de margem. Nao faz streaming nem cache GPU entre chamadas nesta etapa.
O driver ainda pode recusar uma alocacao por concorrencia externa; AUTO faz fallback.
Cancelamento e verificado entre iteracoes; um kernel ja lancado nao e interrompido.

Exemplos de chamadas mantidos:

```sql
CALL algo.degree() LIMIT 10;
CALL algo.pageRank(20) LIMIT 10;
```

Validacao CPU: `cargo test --release --lib --test graph_runtime`.
Validacao GPU (requer DLL/dispositivo): configure NEXUSDB_CUDA_LIBRARY e execute
`cargo test --release --features cuda --test cuda_runtime -- --ignored`.
