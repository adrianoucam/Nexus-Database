# Recuperação após queda do processo e limites de ACID

**Atualização:** a criação bulk recebeu correção de validação integral, commit
SQLite e publicação após commit. Veja [contrato, limites e testes](CORRECAO_BULK.md).
Os resultados iniciais abaixo descrevem o binário anterior à correção.

Este laboratório mede o comportamento do NexusDB real. Não altera o serviço
instalado e não promete ACID completo. Cria processos próprios, credenciais
aleatórias, portas livres e diretórios separados para dois perfis.

```bat
python E:\nexusdb\examples\recovery-Example\demo.py --create-lab
```

Requisitos: Python padrão e binário `E:\nexusdb\target\debug\nexusdb.exe`.
Opcional: `--server CAMINHO`, `--rounds 5`, `--rows 50`, `--output CAMINHO`.
Cada execução preserva os arquivos para inspeção, sem apagar bancos anteriores.
O banco usado é `EXAMPLE_RECOVERY`, com histórico temporal desativado para não
introduzir implicitamente o journal em ambos os perfis.

## O que o teste faz

1. Inicia o perfil `batch1000_journal_off` (batch 1000, journal solicitado off).
2. Envia lote inválido e verifica se o item válido anterior ficou visível.
3. Grava 20 nós por ciclo e registra quais escritas receberam confirmação HTTP.
4. Verifica leitura após escrita por outra conexão HTTP.
5. Executa `kill()` somente no PID criado pelo laboratório, sem flush voluntário.
6. Com o processo parado, executa `PRAGMA integrity_check` nos SQLite encontrados.
7. Reinicia com os mesmos dados e credenciais; compara IDs lógicos e valores.
8. Repete três ciclos e interrompe mais um lote de 500 nós em andamento.
9. Executa tudo novamente com `journal_full_batch1` (journal solicitado on, batch 1).

O código de saída é 0 quando os critérios observados passam e 1 se algum critério
de perda/integridade/atomicidade falhar. O binário corrigido passou; o binário
antigo falhava porque o lote rejeitado deixava um item visível. Não remova esse
critério para produzir um relatório artificialmente aprovado.

No lote em andamento, ausência de resposta significa **resultado desconhecido**:
os dados podem ter sido gravados mesmo que o cliente não tenha recebido sucesso.
Não é correto contabilizar esses registros como perda de escrita confirmada,
nem repetir cegamente uma operação sem estratégia de idempotência.

## Relação com ACID

| Propriedade | Cobertura deste laboratório | Limite |
|---|---|---|
| Atomicidade | Lote rejeitado e lote interrompido: parcial ou tudo/nada | Não equivale a transação de várias requisições |
| Consistência | Valores recuperados e integridade física SQLite | Não verifica todas as regras do grafo/aplicação |
| Isolamento | Leitura após confirmação, por outra conexão | Não testa dirty reads, lost updates ou serialização |
| Durabilidade | Escritas HTTP confirmadas após kill/restart | Não simula energia, disco defeituoso ou cache do hardware |

O SQLite usa WAL/NORMAL em caminhos padrão; o journal solicita FULL nos caminhos
em que é inicializado. Os perfis registram as configurações solicitadas, sem
afirmar que todas as conexões de todos os módulos usam o mesmo synchronous.
O parâmetro synchronous é por conexão, não pode ser confirmado abrindo uma
conexão Python separada e lendo seu próprio PRAGMA.

## Resultados iniciais e interpretação

Em 19/10/2026, três ciclos em cada perfil preservaram 60 nós confirmados por
perfil, sem perda ou alteração observada. As verificações SQLite retornaram ok.
Porém, o lote rejeitado deixou o primeiro item válido visível em ambos os perfis:
**não houve atomicidade integral desse endpoint bulk**. O resultado global é
`failed`, mesmo com durabilidade aprovada no escopo observado.

Relatório inicial:
`E:\nexusdb\target\recovery-validation\run-1792430580606108100\report.json`.

Rodada final, com comparação das escritas anteriores também após a queda durante
o último lote e código de saída 1 para falha:
[relatório final](../../target/recovery-validation/run-1792430621658329800/report.json).

O teste em andamento dessa rodada não recebeu sucesso HTTP e recuperou zero dos
500 registros. Isso observou zero ou todos nesse caso; não prova atomicidade de
qualquer ponto de falha. O teste pode produzir outro resultado em novas rodadas.

## Como ler o relatório

- `lost_acknowledged`: chaves confirmadas ausentes após reiniciar; deve ser vazio.
- `changed_values`: valores confirmados que voltaram diferentes; deve ser vazio.
- `read_after_write`: visibilidade após confirmação.
- `sqlite_integrity`: integridade dos arquivos com processo parado.
- `invalid_batch.partial_visible`: publicação parcial de lote rejeitado.
- `inflight.http_success_received`: houve confirmação antes da queda?
- `inflight.lost_prior_acknowledged`: perda de escritas anteriores nessa última queda.
- `restart_socket_ready_ms`: tempo até o socket abrir; a leitura autenticada vem
  depois. Não é SLA ou medição completa do tempo de recuperação operacional.

## Próximas validações necessárias

Para uma avaliação ACID abrangente, definir primeiro qual API constitui uma
transação e quais garantias ela declara. Depois testar rollback de falha no meio
da operação, leituras concorrentes, atualizações concorrentes, relações sem
endpoints, integridade entre grafo/vetores/histórico e falhas de persistência.
Lotes best-effort precisam de contrato explícito ou de uma alternativa atômica;
um journal por si só não transforma várias operações em uma transação conjunta.

Complementar com encerramento limpo, restauração de backup completo/incremental
e validação de contagem/hash após restauração. Falha de energia exige laboratório
de VM/hardware com critérios próprios; kill do processo não reproduz esse evento.
NPL transacional permanece bloqueada e não deve ser usada como prova de ACID.
