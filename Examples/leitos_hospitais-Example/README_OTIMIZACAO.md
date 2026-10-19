# Otimização experimental de leitos — HSJA fictício

## Aplicativo visual

```powershell
cd E:\nexusdb\examples\leitos_hospitais-Example
python app.py
```

Abre automaticamente `http://127.0.0.1:8766` no navegador. Sem instalação de pacotes. Opções: `--port 8767`, `--no-browser` e `--dataset caminho.zip`. Ctrl+C encerra o servidor local.

Selecione dia, hora e modo para recalcular a proposta. O gráfico mensal calcula 31 snapshots independentes no mesmo horário e modo. O mapa diferencia ocupação histórica, limpeza, disponibilidade e propostas, com filtro por unidade e detalhes de internações/higienização ao clicar no leito. Há bloqueios por IDs, comparação dos cinco modos e exportação JSON do cenário. O cenário não altera os dados originais nem executa transferências. A lista pendente não possui duração de internação prevista, portanto não se inventam permanências para propagar propostas entre dias.

Servidor restrito a loopback, requisições de até 16 KiB, token de sessão, execução serial e cache LRU limitado a 160 cenários por processo. Primeiro cálculo mensal pode levar alguns segundos; a interface informa andamento e bloqueia ações concorrentes. O cache não contém gravações persistentes e é descartado ao encerrar.

Python 3.10+, somente biblioteca padrão, Windows/Linux. Executar nesta pasta:

```powershell
python -m unittest test_optimization.py
python benchmark.py --iterations 3 --output benchmark_resultado.json
python benchmark.py --at "2026-10-31 12:00:00" --blocked L0001,L0002 --output cenario.json
```

Lê o ZIP original sem extraí-lo ou modificá-lo. Esperados: 310 leitos, 236 quartos, 16.000 pacientes e 20.000 atendimentos; volumetria efetiva registrada no JSON. Inspirado em `crud_academico-Example/optimization.py`: separação entre restrições obrigatórias, objetivos, propostas, auditoria e busca reproduzível. Não modifica o servidor nem grava alocações no NexusDB. Este é um benchmark local do domínio hospitalar, não um benchmark do executor nativo do banco. Nenhum banco, credencial ou serviço é necessário.

Compara FIFO convencional, matching bipartido de cardinalidade máxima, fluxo de custo mínimo de cardinalidade máxima, algoritmo genético sobre permutações (seleção, cruzamento e mutação, população 16) e heurística robusta de reservas. Matching não otimiza prioridade. Fluxo prioriza urgência e espera entre soluções de mesma cardinalidade. Genético usa esse mesmo objetivo, sem garantia de ótimo. Robusto reserva demanda prevista de seis horas no pior cenário 0,8x/1x/1,2x; urgências podem consumir reservas. Não é um solver de otimização robusta formal.

Snapshot usa intervalos [entrada, saída), internações anteriores a outubro, censura à direita e término da higienização. Alta sem registro de limpeza bloqueia conservadoramente o leito. Leitos inativos e bloqueados são excluídos. Cada paciente e leito aparecem no máximo uma vez. Solicitações futuras e pacientes já internados são excluídos; duplicatas de paciente retêm o pedido mais antigo. Unidade requerida é restrição obrigatória; campos opcionais de isolamento/ventilador são respeitados. O backlog original não contém requisitos clínicos completos. Não se infere compatibilidade clínica por idade, sexo ou escala.

Previsão: média diária de admissões nos sete dias anteriores ao snapshot, sem eventos futuros. Não é previsão clínica validada. Snapshots são experimentos independentes: backlog acumulado não tem desfechos registrados e propostas anteriores não são consideradas executadas. Transferências não são executadas, quartos coletivos não têm regras de coorte, escalas e cirurgias não são reconciliadas. Não usar para decisões assistenciais.

JSON contém propostas individuais, prioridade atendida, benefício, pendências, auditoria, hash do dataset, OS/CPU/Python, semente, tamanho, estado de cache, snapshot_ms, p50/p95 e pico de memória Python via tracemalloc (não RSS). Medição de tempo inclui overhead de tracemalloc, exclui auditoria e serialização. Iterações repetem a mesma semente para isolar tempo; poucas iterações não sustentam inferências estatísticas. Backend SERIAL_CPU explícito; CUDA/GPU não implementados. Não se afirma melhora de desempenho sem comparar resultados medidos no mesmo ambiente.
