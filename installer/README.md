# Instalador Windows do NexusDB

O arquivo `nexusdb.iss` cria um instalador x64 com Inno Setup 6 ou 7. O pacote:

- instala o executável release em `C:\Program Files\NexusDB\bin`;
- compila o servidor com `--features cuda` e inclui `nexusdb_cuda.dll` junto ao executavel;
- inclui processamento CPU paralelo via Rayon e CUDA opcional para PageRank;
- cria novas configuracoes com backend `AUTO`, preservando configuracoes existentes;
- registra o NexusDB como Windows Service sob `LocalService`;
- cria configuração, dados, backups e logs em `C:\ProgramData\NexusDB`;
- solicita a senha administrativa inicial em campo oculto;
- mantém o servidor restrito a `127.0.0.1:7474` por padrão;
- preserva dados, configuração, backups e logs na desinstalação;
- inclui o manual, README, política de segurança e licença.
- inclui `backup\nexus-backup.cmd`, o aplicativo Python de backup/restore e seu manual;
- inclui a referência dos comandos SQL de usuários, OWNER, GRANT e REVOKE.

## Reempacotar

Este repositorio distribui o pacote pronto e nao inclui os fontes Rust.
Instale Inno Setup 6 ou 7 e disponibilize `target/release/nexusdb.exe` com
suporte CUDA e `target/release/nexusdb_cuda.dll`. Execute na raiz:

```bat
build_installer_windows.bat
```

O resultado fica em `installer/output`. Quando Cargo.toml, fontes Rust e o
diretorio cuda estao presentes, o script recompila o servidor e a DLL; esse
build tambem exige Rust, CUDA Toolkit e Visual Studio C++ Build Tools.

O pacote inclui `Docs/COMPUTE_CPU.md` e `conf_examples/nexusdb_compute.conf`.
No destino, CUDA exige GPU NVIDIA compativel com compute_75 ou superior e
um driver compativel com o Toolkit do build. O Toolkit nao precisa estar
instalado no destino. AUTO usa CPU se CUDA nao estiver disponivel.
Degree usa CPU; CUDA explicito suporta somente PageRank.

O instalador e seu SHA-256 estao em `output/` e na release `v0.1.1`.

## Backup por terminal

O atalho **Backup e restore (terminal)** abre a ajuda do aplicativo. Também pode
executar `"C:\Program Files\NexusDB\backup\nexus-backup.cmd" --help`.
É necessário Python 3.10 ou posterior, disponível pelo launcher `py -3`, ou
indicado na variável `NEXUSDB_BACKUP_PYTHON`. O instalador não baixa Python.
O servidor não depende de Python.

Para incrementais e PITR, configure `NEXUSDB_RECOVERY_JOURNAL=1` no arquivo do
serviço e reinicie o serviço em uma janela planejada. A ativação é opcional e
não é feita automaticamente pelo instalador. Siga o manual de backup para criar
o full inicial e arquivar os incrementais. O restore exige um diretório novo.
O usuário que executa o backup precisa de leitura dos dados e escrita no repositório.

## Atualização e desinstalação

Durante uma atualização, o instalador para o serviço de forma graciosa, troca o
binário e volta a iniciá-lo. A senha informada no assistente serve apenas para o
bootstrap de uma instalação ainda não inicializada e não redefine a senha de um
banco existente.

A desinstalação remove o serviço e os arquivos de programa. O diretório
`C:\ProgramData\NexusDB` é intencionalmente preservado. Exclua-o manualmente
somente se também quiser apagar definitivamente bancos, credenciais, backups e
logs.
