# NexusDB — instalador Windows

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
