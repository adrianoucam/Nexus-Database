# Instalador Windows do NexusDB

O arquivo `nexusdb.iss` cria um instalador x64 com Inno Setup 6 ou 7. O pacote:

- instala o executável release em `C:\Program Files\NexusDB\bin`;
- registra o NexusDB como Windows Service sob `LocalService`;
- cria configuração, dados, backups e logs em `C:\ProgramData\NexusDB`;
- solicita a senha administrativa inicial em campo oculto;
- mantém o servidor restrito a `127.0.0.1:7474` por padrão;
- preserva dados, configuração, backups e logs na desinstalação;
- inclui o manual, README, política de segurança e licença.

## Compilar

Abra um terminal na raiz do projeto e execute:

```bat
build_installer_windows.bat
```

O script compila o NexusDB em release quando necessário e grava o instalador em
`installer\output`.

## Atualização e desinstalação

Durante uma atualização, o instalador para o serviço de forma graciosa, troca o
binário e volta a iniciá-lo. A senha informada no assistente serve apenas para o
bootstrap de uma instalação ainda não inicializada e não redefine a senha de um
banco existente.

A desinstalação remove o serviço e os arquivos de programa. O diretório
`C:\ProgramData\NexusDB` é intencionalmente preservado. Exclua-o manualmente
somente se também quiser apagar definitivamente bancos, credenciais, backups e
logs.

## Atualizacao do instalador: backup e usuarios SQL

O script atualizado esta em `installer/nexusdb.iss`; o `nexusdb.iss` da raiz
oferece a mesma configuracao com caminhos relativos a raiz. Inclui a ferramenta de terminal `backup_app/` e o manual
`Docs/SQL_USERS_AND_GRANTS.md`.

Este repositorio de distribuicao nao inclui os fontes Rust do servidor.
Para gerar o instalador, disponibilize um `nexusdb.exe` release atualizado em
`target/release/nexusdb.exe`, instale Inno Setup 6 ou 7 e execute
`build_installer_windows.bat`. Se os fontes e Cargo.toml estiverem presentes,
o script compila o servidor antes de empacotar.

O backup requer Python 3.10+ na maquina onde for utilizado. Usuarios e permissoes
SQL ainda sao locais a cada no do cluster. Consulte os manuais incluidos.
O executavel antigo em `output/` nao e atualizado por esta alteracao dos scripts.
O novo instalador sera gerado em `installer/output/`.
