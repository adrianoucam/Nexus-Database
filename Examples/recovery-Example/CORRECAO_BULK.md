# Correção de atomicidade dos endpoints bulk

## Contrato corrigido

`POST /db/data/node/bulk` e `POST /db/data/relationship/bulk` passam a rejeitar
todo o lote quando algum item falha na validação de entrada. Retornam HTTP 400,
`code: BULK_VALIDATION_FAILED`, `processados: 0`, `resultados: []` e a lista de
erros por índice. O antigo comportamento `partial_error`, gravando apenas itens
válidos, foi removido desses dois caminhos. Lotes válidos preservam o envelope
de sucesso, IDs, chaves do cliente e ordem dos resultados.

Na camada de modelo, todos os itens são preparados sem alterar o grafo. Labels,
tipos, propriedades e endpoints são validados antes da publicação. Cada lote é
persistido em uma única transação SQLite; falha em qualquer INSERT desfaz o lote.
Somente após COMMIT os nós/relações, índices e revisão do grafo são publicados,
mantendo o lock do modelo durante essa sequência. Leitores que usam esse lock
não observam prefixos nem escritas ainda não confirmadas.

O caminho atômico usa `synchronous=FULL` e o journal de recuperação já existente,
independentemente do tamanho de buffer solicitado. O journal é ativado no banco
e permanece ativo após reiniciar. SQLite passa a ser a autoridade para recuperação;
o lote não é anexado antes do commit ao JSONL e não entra na fila de retry.
Isso impede ressuscitar linhas de uma transação desfeita. Os arquivos JSONL
legados continuam sendo reconciliados no startup conforme o contrato do journal.

Snapshots e replicação mantêm seus caminhos internos anteriores. Não são
transformados implicitamente em transações locais com o mesmo contrato bulk.
O valor `recovery_journal: 0` no laboratório descreve a configuração solicitada;
o primeiro bulk válido agora ativa o journal necessário à garantia desse endpoint.

## Escopo e limites

Essa correção cobre criação bulk de nós e relacionamentos, inclusive rollback de
falha de persistência e publicação em memória. Não implementa uma transação que
envolva várias requisições HTTP, nem habilita escrita transacional NPL.

A replicação HA acontece depois do commit local. Se ela falhar ou a conexão cair
antes da resposta, o cliente pode receber erro mesmo com commit local concluído.
Não repetir cegamente esse pedido: chaves do cliente retornadas pelo bulk não
são uma garantia de idempotência. Não há alegação de ACID distribuído ou Raft.

Operações individuais de update/delete, instalação de snapshot, escrita Cypher,
vetores e política de conhecimento têm contratos próprios. É necessária auditoria
específica antes de declarar ACID global do banco. Kill/restart testa falha de
processo, sem reproduzir corte de energia, falha física de disco ou corrupção.

## Testes de regressão

`tests/bulk_atomicity_runtime.rs` usa processo filho e diretório de dados isolado.
Testa HTTP inválido sem gravação parcial, validação da API Rust, endpoints
inexistentes, erro SQLite injetado no segundo INSERT de nós/relações, rollback
do journal, IDs/revisão inalterados após erro, flush sem ressuscitar registros,
recarga, escritores concorrentes e visibilidade de lotes completos.

```bat
cd E:\nexusdb
cargo test --features knowledge,phronesis,datalog --test bulk_atomicity_runtime
cargo build --features knowledge,phronesis,datalog
python E:\nexusdb\examples\recovery-Example\demo.py --create-lab
```

Os relatórios anteriores com `failed` permanecem como evidência da falha original;
não devem ser sobrescritos ou tratados como resultados do novo binário.

## Resultado do binário corrigido — 19/10/2026

- `cargo check --features knowledge,phronesis,datalog` passou.
- **114 testes de biblioteca e sete testes de integração passaram**, incluindo
  o novo teste de atomicidade e os testes de conhecimento, consultas, vetores e
  histórico temporal. [Log Rust](../../target/bulk-acid-rust-tests.log).
- O binário `target/debug/nexusdb.exe` foi recompilado com essas funcionalidades
  pelo Cargo durante a validação.
- Três ciclos de kill/restart por perfil preservaram **60 registros confirmados
  por perfil**, sem perda ou alteração. Os SQLite verificados retornaram `ok`.
- O lote inválido foi rejeitado **sem publicação parcial** nos dois perfis.
- Nas duas quedas durante escrita de 500 registros, não houve confirmação HTTP;
  recuperaram-se zero registros desse lote e preservaram-se todos os anteriores.
  Isso é resultado desconhecido para o cliente, não perda de escrita confirmada.
- Resultado global: **passed_observed_scope**, código de saída 0.

[Relatório após correção](../../target/recovery-validation/run-1792431054062182900/report.json).
Não foram alterados serviços instalados, dados de produção ou configurações do
usuário fora dos processos de teste.
