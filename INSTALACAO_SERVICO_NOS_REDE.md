# NexusDB como serviço Windows nos nós da rede

Este guia descreve a instalação de um cluster HA de três computadores Windows,
com um serviço NexusDB por computador. Baseado na implementação atual do projeto.
Instalar o serviço sozinho não configura o cluster: o padrão é `SINGLE`, com
escuta em `127.0.0.1:7474`.

## 1. O que instalar em cada computador

Use **o mesmo instalador e a mesma compilação** em todos os nós. Baixe o arquivo
`NexusDB-<versao>-windows-x64-setup.exe` da Release privada ou copie o instalador
validado para cada máquina. Os nós não precisam acessar o GitHub continuamente.

| Componente | Necessário no nó? |
|---|---|
| NexusDB pelo instalador Inno Setup | Sim |
| Rust, Cargo, Visual Studio, Inno Setup e fontes Rust | Não; são usados na máquina de compilação |
| DLL `nexusdb_cuda.dll` | Já acompanha o instalador |
| GPU NVIDIA e driver compatível | Somente para utilizar CUDA naquele nó |
| CUDA Toolkit / `nvcc` | Não para executar; somente para compilar a DLL |
| Python 3.10+ | Somente para executar o aplicativo de backup Python |
| PyInstaller | Não |

O servidor funciona sem Python. O utilitário de backup permanece em Python,
conforme a distribuição atual.

## 2. Planejar os endereços

Exemplo: substitua estes IPs pelos endereços reais da sua rede.

| Nó | IP fixo ou reservado no DHCP | ID HA | Porta TCP |
|---|---|---|---|
| node1 | 192.168.1.21 | 1 | 7474 |
| node2 | 192.168.1.22 | 2 | 7474 |
| node3 | 192.168.1.23 | 3 | 7474 |

Computadores diferentes podem utilizar a mesma porta. Cada nó lista os outros
dois em `NEXUSDB_HA_PEERS`, sem incluir a si próprio. Não use `localhost` ou
`127.0.0.1` para identificar outro computador. O líder é eleito: ID 1 não
significa líder permanente.

Este exemplo é de rede privada confiável ou VPN. A implementação atual de HA
usa HTTP entre os membros; o segredo autentica a comunicação, mas não a cifra.
Não exponha a porta diretamente à internet. `NEXUSDB_ALLOW_INSECURE_REMOTE=true`
autoriza explicitamente a escuta HTTP remota; não habilita TLS.

## 3. Instalar o serviço em cada nó

1. Execute o instalador como Administrador, preferencialmente no destino padrão.
2. Defina a senha administrativa solicitada pelo instalador.
3. Em uma instalação nova, desmarque **Iniciar o serviço NexusDB ao concluir**
   para configurar HA antes do primeiro início.
4. Abra PowerShell como Administrador e edite o arquivo abaixo.

```powershell
notepad "$env:ProgramData\NexusDB\config\nexusdb.env"
```

O instalador registra o serviço, configura início automático atrasado e recuperação
após falha. A conta utilizada é `NT AUTHORITY\LocalService`, com acesso restrito.
Não é necessário executar novamente `service install` quando o instalador já
registrou o serviço.

| Conteúdo | Caminho padrão |
|---|---|
| Servidor e DLL CUDA | `C:\Program Files\NexusDB\bin` |
| Configuração do serviço | `C:\ProgramData\NexusDB\config\nexusdb.env` |
| Bancos e estado local | `C:\ProgramData\NexusDB\data` |
| Backups | `C:\ProgramData\NexusDB\backups` |
| Log | `C:\ProgramData\NexusDB\logs\nexusdb.log` |

Use armazenamento local independente em cada nó. Não compartilhe a mesma pasta
de dados entre serviços, nem copie o estado `_cluster` de outro nó. Se mudar os
caminhos, conceda à conta `LocalService` as permissões necessárias; o instalador
prepara os caminhos padrão.

## 4. Configurar HA em cada `nexusdb.env`

**Edite as chaves existentes, sem duplicá-las.** Preserve os caminhos e as opções
de log criados pelo instalador. Coloque todas as variáveis `NEXUSDB_*` antes das
seções `[compute]` e `[compute.cuda]`, se essas seções existirem.

Adicione/ajuste este bloco comum nos três nós:

```dotenv
NEXUSDB_MODE=HA
NEXUSDB_HA_CLUSTER_AUTH=true
NEXUSDB_HA_STRICT=true
NEXUSDB_HA_READ_REPLICAS=true
NEXUSDB_HA_ALLOW_SINGLE_NODE_LEADER=false
NEXUSDB_ALLOW_INSECURE_REMOTE=true
NEXUSDB_HA_SECRET=SUBSTITUA_PELO_SEGREDO_REAL_DO_CLUSTER
```

O segredo deve ser **idêntico nos três nós**, com pelo menos 32 caracteres.
Para um cluster existente, utilize o segredo já configurado: não gere um novo
somente no nó que está entrando. Para um cluster novo, gere um segredo aleatório
uma vez e distribua-o por meio seguro. Não use o texto de exemplo como segredo.

Configure também as três chaves específicas de cada máquina:

### node1 — 192.168.1.21

```dotenv
NEXUSDB_HA_SERVER_ID=1
NEXUSDB_HTTP_ADDR=192.168.1.21:7474
NEXUSDB_HA_PEERS=http://192.168.1.22:7474,http://192.168.1.23:7474
```

### node2 — 192.168.1.22

```dotenv
NEXUSDB_HA_SERVER_ID=2
NEXUSDB_HTTP_ADDR=192.168.1.22:7474
NEXUSDB_HA_PEERS=http://192.168.1.21:7474,http://192.168.1.23:7474
```

### node3 — 192.168.1.23

```dotenv
NEXUSDB_HA_SERVER_ID=3
NEXUSDB_HTTP_ADDR=192.168.1.23:7474
NEXUSDB_HA_PEERS=http://192.168.1.21:7474,http://192.168.1.22:7474
```

Os exemplos vinculam o servidor ao IP específico da máquina. Nesse caso, consulte
a saúde usando esse IP, não `127.0.0.1`. Se optar por `0.0.0.0:7474`, o servidor
escutará em todas as interfaces; mantenha o acesso limitado pelo firewall.

**Configuração do serviço não é a configuração do terminal:** definir
`$env:NEXUSDB_MODE` numa janela PowerShell ou executar um `run_node*.bat` não
configura o serviço Windows. Use o `nexusdb.env`. Variáveis já presentes no
ambiente do processo têm prioridade sobre o arquivo; confira variáveis de
ambiente da máquina se o comportamento não corresponder à configuração.

A senha administrativa inicial é independente do segredo HA. Em uma instalação
nova, mantenha `NEXUSDB_ADMIN_PASSWORD` até o primeiro início bem-sucedido.
Depois remova essa linha ou deixe-a vazia: o hash já estará persistido. O instalador
limpa a senha de bootstrap quando ele próprio consegue iniciar o serviço.
Não suponha que a replicação dos dados configure automaticamente as credenciais
administrativas de cada máquina.

## 5. Liberar a comunicação no firewall

No PowerShell elevado de cada nó, crie uma regra restrita aos IPs do cluster
(ajuste os IPs, a porta e os perfis à sua rede):

```powershell
New-NetFirewallRule -DisplayName "NexusDB HA TCP 7474" `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 7474 `
  -RemoteAddress 192.168.1.21,192.168.1.22,192.168.1.23 `
  -Profile Domain,Private
```

Execute a criação uma vez por máquina. Para clientes e computadores de
administração, adicione regras específicas com seus IPs autorizados. Não abra
para qualquer origem. Se houver bloqueio de saída, autorize também as conexões
entre membros na mesma porta. Mantenha a classificação de rede compatível com
os perfis da regra, sem alterar o perfil de uma rede não confiável apenas para
contornar o firewall.

Depois de iniciar os serviços, teste a partir de cada nó os outros dois:

```powershell
Test-NetConnection 192.168.1.22 -Port 7474
Test-NetConnection 192.168.1.23 -Port 7474
```

## 6. Iniciar e validar o cluster

Execute em **cada computador**, no PowerShell elevado:

```powershell
$nexus = "$env:ProgramFiles\NexusDB\bin\nexusdb.exe"
& $nexus service start
& $nexus service status
```

Não execute simultaneamente o serviço e os batches `run_node*.bat` utilizando
as mesmas portas ou pastas. O batch `run_cluster_ha.bat` é para processos locais,
não para instalar serviços nos computadores da rede.

Inicie os três membros e aguarde a eleição/sincronização. Com a configuração
estrita de três membros, a maioria é dois; um nó isolado não deve ser forçado
a assumir liderança. Consulte a saúde, a partir de um IP autorizado:

```powershell
Invoke-RestMethod http://192.168.1.21:7474/cluster/health
Invoke-RestMethod http://192.168.1.22:7474/cluster/health
Invoke-RestMethod http://192.168.1.23:7474/cluster/health
```

O endpoint de saúde não exige senha. Procure um líder com `role = LEADER` e
`ready = true`; os demais membros devem convergir para o mesmo `leader_id`.
O endpoint `/cluster/leader` fornece detalhes adicionais e exige autenticação
administrativa. Estado `Running` no Windows confirma o processo, não a prontidão
do cluster nem a conclusão do catch-up.

O HA implementa catch-up por WAL/snapshot. Antes de encaminhar clientes para
um nó novo, confirme sua saúde e compare uma consulta conhecida com o líder.
Use um nó novo sem dados independentes conflitantes. Transformar três bancos
`SINGLE` já populados em HA não combina automaticamente seus conteúdos.

As aplicações devem descobrir/acompanhar o líder para operações de escrita.
Não fixe permanentemente o node1 como destino de escrita supondo que sempre
será o líder.

## 7. CUDA nos outros nós

CUDA é **local ao computador que executa a consulta**. Uma GPU no node1 não
acelera automaticamente uma consulta executada no node2 ou node3.

Mantenha a DLL ao lado de `nexusdb.exe` e utilize `AUTO`. Exemplo de seções ao final
do `nexusdb.env` (ajuste recursos à capacidade de cada máquina):

```ini
[compute]
backend = "AUTO"
threads = 4
memory_mb = 256
max_jobs = 2
timeout_ms = 30000

[compute.cuda]
enabled = true
```

Não duplique essas opções com variáveis `NEXUSDB_COMPUTE_*` equivalentes.
Em nós sem GPU/driver compatível, o modo `AUTO` utiliza CPU. O modo explícito
`CUDA` pode retornar erro quando indisponível; não é o indicado para um cluster
com máquinas diferentes. O build atual da DLL exige dispositivo compatível
com compute capability 7.5 ou posterior e driver compatível com o Toolkit usado
na compilação.

`CALL algo.degree();` tenta CUDA em `AUTO` a partir de 100 mil vértices e
1 milhão de arestas. Grafos menores usam CPU. Confira `execution.selected_backend`
e `execution.fallback` no resultado. Reinicie o serviço após trocar a DLL ou
alterar a configuração; a resolução do módulo é armazenada por processo.

## 8. Aplicativo de backup Python

O backup continua sendo uma ferramenta separada; **não é automaticamente um
serviço nem uma tarefa agendada**. Instale Python 3.10+ nas máquinas em que
for executar o backup e teste:

```powershell
& "$env:ProgramFiles\NexusDB\backup\nexus-backup.cmd" --help
```

Se o launcher `py` não estiver disponível, configure o caminho real do Python:

```powershell
$env:NEXUSDB_BACKUP_PYTHON = 'C:\Python312\python.exe'
& "$env:ProgramFiles\NexusDB\backup\nexus-backup.cmd" --help
```

Substitua o caminho pelo Python instalado. Para agendar, configure o Agendador
de Tarefas com uma conta que tenha acesso às pastas de dados/backup e aos recursos
necessários. Não conte com variáveis do seu terminal nem unidades de rede
mapeadas na sua sessão. Consulte `backup_app/README.md` no projeto ou o manual
instalado em `C:\Program Files\NexusDB\backup\README.md` antes de definir o job.
Replicação HA não substitui backup independente.

## 9. Atualizar os nós com a nova compilação

Gere/publique o pacote uma única vez na máquina de compilação com
`atualizar_instalador_github.bat`. Distribua exatamente esse instalador para todos
os nós; não é necessário recompilar em cada máquina.

1. Faça backup e confira saúde, líder atual e sincronização dos membros.
2. Confirme a compatibilidade de protocolo e formato de dados entre as versões.
   Se ela não estiver estabelecida, use janela de manutenção; não presuma que
   qualquer mudança permita atualização gradual sem interrupção.
3. Para versões compatíveis, atualize um seguidor por vez. O instalador para o
   serviço existente, troca os arquivos e tenta reiniciá-lo, mesmo que a opção
   de início esteja desmarcada numa atualização.
4. Espere esse nó voltar e concluir o catch-up antes de atualizar o próximo.
5. Atualize o líder por último e acompanhe a nova eleição. Pode ocorrer uma
   interrupção breve; os clientes precisam lidar com mudança de líder e retries.
6. Confirme os três nós saudáveis e com a mesma compilação. Compare hashes dos
   executáveis quando necessário; a versão textual pode ser igual entre builds.

Com três membros, não desligue dois simultaneamente numa atualização gradual.
O instalador preserva os dados e a configuração existentes; confira os valores
HA após a atualização. Não substitua `nexusdb.env` por um arquivo genérico nem
apague a pasta `data` para atualizar.

## 10. Comandos de manutenção e diagnóstico

```powershell
$nexus = "$env:ProgramFiles\NexusDB\bin\nexusdb.exe"
& $nexus service status
& $nexus service stop
& $nexus service start
# Alternativa para aplicar uma configuracao alterada:
& $nexus service restart

Get-Content "$env:ProgramData\NexusDB\logs\nexusdb.log" -Tail 100
```

Execute somente a operação desejada; não é necessário parar/iniciar/reiniciar
em sequência. Prefira parada graciosa, que realiza flush.

| Sintoma | Conferir |
|---|---|
| Serviço não inicia | Log; senha inicial; segredo HA; IP configurado; porta ocupada; ACLs dos caminhos |
| Funciona só localmente | `NEXUSDB_HTTP_ADDR`, autorização de HTTP remoto, firewall e perfil de rede |
| Não encontra os outros nós | IPs/portas reais em peers; não usar localhost; teste TCP entre membros |
| Não há líder pronto | Maioria disponível, segredo comum, IDs únicos, peers consistentes e logs |
| Nó novo tem dados diferentes | Catch-up, saúde e consultas de validação; não copiar arquivos em uso |
| CUDA usa CPU | Modo AUTO, tamanho do grafo, DLL, driver e motivo registrado no resultado |
| Backup não executa | Python/launcher, caminho do interpretador e permissões da conta da tarefa |

Para uma expansão além destes três membros, planeje os peers e o quórum de todos
os participantes. Este guia não implementa reconfiguração dinâmica de membros.

## Referências do projeto

- `src/windows_service.rs`: registro, conta, caminhos e ciclo do serviço.
- `src/server_runtime.rs`: leitura da configuração e escuta HTTP.
- `src/ha.rs`: peers, eleição, quórum e sincronização.
- `installer/nexusdb.iss`: instalação, atualização e início do serviço.
- `Docs/COMPUTE_CPU.md`: CPU/CUDA e telemetria.
- `ATUALIZAR_INSTALADOR_GITHUB.md`: geração e publicação dos pacotes.
- `backup_app/README.md`: uso e limites do backup/restore.
