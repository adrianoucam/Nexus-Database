# NexusDB Backup — ferramenta de terminal

Aplicativo separado para **backup completo por banco**, incrementais lógicos,
arquivamento contínuo, verificação e recuperação até um instante (PITR).
Python 3.10 ou superior, sem dependências de terceiros. Funciona em Windows e Linux.

Esta é uma primeira implementação para o armazenamento SQLite do NexusDB;
não é uma implementação do WAL nem dos utilitários do PostgreSQL.

## Iniciar

No Windows, com o launcher Python `py` instalado:

```bat
E:\nexusdb\backup_app\nexus-backup.cmd --help
```

Se `py` não estiver instalado, defina o caminho de um Python real (não o atalho
da Microsoft Store):

```bat
set "NEXUSDB_BACKUP_PYTHON=C:\caminho\python.exe"
E:\nexusdb\backup_app\nexus-backup.cmd --help
```

Também pode executar diretamente, inclusive no Linux:

```text
python nexus_backup.py --help
```

O script `nexus_backup.py` é o aplicativo distribuível. Copie `backup_app` para
a outra máquina; o código-fonte Rust só é necessário para compilar o servidor.
Senhas não são gravadas nos backups pelo aplicativo nem passadas como argumentos.

## Ativar o histórico no servidor

Compile o servidor desta revisão com `cargo build --release` e acrescente ao
arquivo `.conf` do nó que será a origem dos backups:

```ini
NEXUSDB_RECOVERY_JOURNAL=1
```

Antes da primeira ativação em um banco legado, encerre a versão anterior
graciosamente (com flush), para consolidar seu buffer/JSONL no SQLite.
Reinicie esse nó uma vez para carregar a versão e configuração novas. Em HA,
habilite em todos os nós se quiser poder escolher qualquer nó como origem, mas
mantenha cada cadeia de backup vinculada ao mesmo nó e à mesma encarnação do banco.

Depois dessa ativação, os backups não exigem desligar o servidor. O diário fica
no SQLite, na mesma transação das alterações, com triggers para nós e arestas.
São registrados insert/upsert, update, delete, exclusões em lote e truncate.
Rollback elimina também os registros do diário.

O modo usa `synchronous=FULL` e persiste escritas individuais antes de retornar,
em vez de deixá-las somente no buffer de flush. Isso tem custo de I/O. Operações
em lote continuam agrupadas. Uma vez criado, o diário permanece ativo naquele
banco mesmo se a variável for removida. Não execute um binário antigo sobre ele:
as triggers rejeitam escritas que não informam a transação de recuperação.
Nesse modo o SQLite passa a ser a fonte autoritativa, inclusive no reinício;
JSONL antigo não é importado sobre transações confirmadas.

O PITR não recupera períodos anteriores à ativação ou alterações que ainda não
foram arquivadas. DROP/recriação e instalação de snapshots iniciam uma nova
encarnação; a ferramenta exige um novo full, sem misturar históricos.

## Backup completo online

Exemplo para `AIRROUTES` no node2. Ajuste o nome ao seu banco real:

```bat
nexus-backup.cmd backup --type full ^
  --data-root E:\nexusdb\runtime\node2\data ^
  --database AIRROUTES ^
  --repo E:\nexusdb-backups\AIRROUTES
```

O resultado JSON inclui `id`, contagens, `end_tx` e `covered_ms`. Guarde o ID.
O pacote `<id>.nxb` contém um SQLite consistente e um manifest com SHA-256.
Ele é produzido pela API SQLite Online Backup; copiar simplesmente o `.sqlite`
enquanto há WAL ativo não é equivalente.

Para um servidor legado sem diário, é permitido **somente full**:

```bat
nexus-backup.cmd backup --type full ^
  --data-root E:\nexusdb\runtime\node2\data ^
  --database AIRROUTES --repo E:\nexusdb-backups\AIRROUTES ^
  --flush-url http://127.0.0.1:7475 --user admin
```

A senha é pedida de forma oculta, ou lida de `NEXUSDB_PASSWORD`. A URL deve ser
do MESMO nó de `--data-root`, acessível localmente. O backup cobre o estado
persistido capturado; escritas concorrentes posteriores ao flush podem ficar
fora dele. Para uma origem parada, use `--offline` em vez de `--flush-url`.

O repositório deve ficar fora da pasta do banco. Preferencialmente mantenha uma
cópia dos pacotes em outro disco ou máquina.

## Incremental

```bat
nexus-backup.cmd backup --type incremental ^
  --data-root E:\nexusdb\runtime\node2\data ^
  --database AIRROUTES --repo E:\nexusdb-backups\AIRROUTES ^
  --parent ID_DO_FULL_OU_ULTIMO_INCREMENTAL
```

Somente as transações posteriores ao ancestral são armazenadas no incremental.
São conferidos a identidade da origem, schema, IDs consecutivos, horários
monotônicos e contagem de eventos por transação. Um log truncado, um ancestral
ausente ou uma mudança de schema exige intervenção ou um novo full.

Cada pacote aponta para o SHA-256 do pacote anterior. Copie **o full e todos os
incrementais ancestrais**, não somente o último arquivo.

## Arquivamento contínuo para PITR

```bat
nexus-backup.cmd archive ^
  --data-root E:\nexusdb\runtime\node2\data ^
  --database AIRROUTES --repo E:\nexusdb-backups\AIRROUTES ^
  --parent ID_DO_ULTIMO_BACKUP --interval 30
```

Esse processo fica ativo no terminal, publica um incremental a cada ciclo e
mostra seu ID. `Ctrl+C` encerra; pacotes já publicados continuam válidos.
`--once` captura um único ciclo. Após reiniciar o processo, use como `--parent`
o último ID concluído, consultável por `list`.

A frequência de captura determina a janela de perda se a máquina de origem
for perdida. Ela não garante RPO de 30 segundos: tempo de execução, carga e
falhas também contam. Não há agendamento instalado automaticamente.

O diário local não é podado automaticamente nesta versão. Monitore espaço,
faça novos fulls periodicamente e preserve os ancestrais de cada cadeia retida.
Não apague registros das tabelas `recovery_*` manualmente.

## Listar e verificar

```bat
nexus-backup.cmd list --repo E:\nexusdb-backups\AIRROUTES
nexus-backup.cmd verify --repo E:\nexusdb-backups\AIRROUTES --backup ID_FINAL
```

`verify` confere os hashes, monta a cadeia em uma pasta temporária, reproduz os
eventos e executa `integrity_check` e `foreign_key_check`. Não altera a origem.
Pacotes `.partial` nunca são considerados backups publicados. Um lock deixado
por falha de processo deve ser removido apenas após confirmar que o escritor
correspondente não está mais ativo.

## Restauração total / última posição arquivada

Na máquina de destino, usando a mesma versão do NexusDB inicialmente:

```bat
nexus-backup.cmd restore --repo D:\backups\AIRROUTES ^
  --backup ID_FINAL ^
  --destination D:\nexusdb-recuperado\data\AIRROUTES
```

O destino **não pode existir**. O aplicativo reconstrói uma cópia temporária,
valida-a e publica a pasta final com `nexusdb.sqlite` e `restore-report.json`.
Não substitui um banco que esteja sendo servido por uma instância em execução.

Inicie uma instância SINGLE do NexusDB com:

```ini
NEXUSDB_DATA_ROOT=D:\nexusdb-recuperado\data
NEXUSDB_MODE=SINGLE
NEXUSDB_RECOVERY_JOURNAL=1
```

Configure o admin da nova instância separadamente. Ela carrega os dados e
reconstrói os índices derivados em memória. Faça consultas de validação antes
de apontar clientes para ela. A origem pode continuar online durante todo esse
procedimento. Um banco restaurado recebe uma nova identidade de diário e deve
iniciar sua própria cadeia com um full novo.

## Point-in-time recovery

```bat
nexus-backup.cmd restore --repo D:\backups\AIRROUTES ^
  --backup ID_FINAL ^
  --at "2026-09-24T15:30:00-03:00" ^
  --destination D:\nexusdb-recuperado\data\AIRROUTES_PITR
```

O instante deve estar entre a posição do full escolhido e a última transação
arquivada na cadeia. Para recuperar antes do full, escolha um full anterior.
`--at` aceita ISO 8601 com fuso obrigatório. A ferramenta aplica transações
inteiras com timestamp lógico de commit menor ou igual ao alvo, sem cortar
uma operação em lote. Fora da cobertura, ela falha em vez de aproximar o horário
silenciosamente. Para o último estado arquivado, omita `--at`.

O timestamp é atribuído imediatamente ANTES do COMMIT SQLite e armazenado na
mesma transação; ele é monotônico por banco. Não representa o instante exato de
confirmação HTTP nem o commit de consenso HA. Uma requisição HTTP com múltiplas
transações físicas pode produzir múltiplos pontos recuperáveis. Não há garantia
de snapshot distribuído ou consistência transacional entre bancos diferentes.

## Escopo e limites

- Backup completo = arquivo SQLite completo de UM banco, com tabelas, dados e
  índices SQLite. Incrementais/PITR cobrem os dados de nós e relacionamentos.
- Usuários, senhas, permissões (`system/nexusdb_config.sqlite`), configuração de
  serviços e estado do cluster não fazem parte do backup por banco.
- Definições de índices de propriedades mantidas apenas em memória pelo servidor
  atual não são exportadas. Reaplique seus comandos `CREATE INDEX` após restaurar.
- Metadados administrativos fora das tabelas de dados não têm replay incremental.
  Não há recuperação automática de exclusão do próprio arquivo/banco depois do
  último arquivo de histórico efetivamente arquivado.
- As cadeias são locais a um nó. Não una incrementais de líderes diferentes
  após failover. Faça um novo full no novo nó de origem.
- Restore não instala dados automaticamente nos três membros de um cluster.
  Valide primeiro numa instância SINGLE isolada; a formação/sincronização de um
  novo cluster é uma etapa operacional separada.
- Os arquivos são comprimidos, mas não criptografados nem assinados. SHA-256
  detecta corrupção; não substitui controle de acesso a um repositório confiável.
- A leitura usa snapshot SQLite online. Não para o servidor, mas consome I/O e
  pode prolongar retenção do WAL enquanto dura a captura. Não há promessa de
  impacto zero na latência.

## Testes

```text
python -m unittest discover -s backup_app -v
cargo test --release --lib --test graph_runtime --test grasp_runtime
python backup_app/integration_test.py --server target/release/nexusdb.exe
```

O teste ponta a ponta inicia instâncias temporárias, grava pelo HTTP real, gera
full/incrementais, recupera antes de uma exclusão e inicia o banco restaurado
em outra pasta. Ele não usa os bancos do seu cluster.
