# NexusDB 0.1.1 — CUDA e processamento paralelo

- Instalador Windows x64 inclui o servidor compilado com suporte CUDA e a DLL
  `nexusdb_cuda.dll`, com runtime CUDA estatico.
- Degree e PageRank podem usar varios nucleos da CPU por meio do pool de threads
  Rayon. PageRank tambem pode executar na GPU NVIDIA.
- Novas instalacoes usam backend AUTO; configuracoes de instalacoes anteriores
  sao preservadas.
- O arquivo de configuracao aceita `[compute]` e `[compute.cuda]`, incluindo
  limites de threads, memoria estimada, trabalhos simultaneos, prazo e ativacao CUDA.
- README, referencia de compute e exemplo de configuracao acompanham o pacote.

CUDA requer Windows x64, GPU NVIDIA compativel com compute capability 7.5 ou
superior e driver compativel com o Toolkit usado na compilacao. Este pacote foi
compilado com CUDA Toolkit 13.3. Nao e necessario instalar o Toolkit no destino.
AUTO usa CPU quando a GPU nao esta disponivel ou quando as heuristicas indicam
CPU. Degree nao possui kernel CUDA; backend CUDA explicito retorna
`CUDA_UNSUPPORTED_OPERATION` para essa operacao.

Consulte `execution.selected_backend` nas respostas para verificar o backend
efetivo. O paralelismo CPU ocorre dentro do processo; nao representa execucao
distribuida da consulta. O projeto continua experimental.

Arquivos da release:

- `NexusDB-0.1.1-windows-x64-setup.exe`
- `NexusDB-0.1.1-windows-x64-setup.exe.sha256`
