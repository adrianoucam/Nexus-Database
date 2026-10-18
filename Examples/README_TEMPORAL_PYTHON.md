# Demonstração Python de grafos temporais

`temporal_graph_demo.py` demonstra os conceitos da proposta Pometry fornecida
usando as APIs reais do NexusDB. Não integra nem reproduz o produto Pometry.

## Executar

No diretório do NexusDB:

```powershell
cargo build --bin nexusdb
python -m pip install pyarrow
python examples/temporal_graph_demo.py --server target/debug/nexusdb.exe --patients 50 --seed 42 --output temporal-python-output
```

PyArrow 26.0.0 foi usado na validação. O programa imprime os passos em
português e gera um diretório `run-...` novo a cada execução.
O executável padrão é localizado a partir do repositório onde o script está,
independentemente da pasta atual. Também é possível executar dentro de examples:

```powershell
py temporal_graph_demo.py --patients 50 --seed 42 --output temporal-python-output
```

Um caminho explícito em --server e a pasta --output continuam relativos à
pasta atual, quando não forem absolutos. Se o executável não existir, o
programa informa como compilá-lo ou fornecer outro caminho.
Abra o arquivo **temporal_graph.html** para explorar a linha do tempo e
alternar entre o estado conhecido antes e depois da correção. O HTML
funciona offline, sem instalar bibliotecas de visualização.

## O que demonstra

1. Database `EXAMPLE_TEMPORAL_PYTHON` com histórico habilitado somente nele.
2. Checkpoint e watermark de confirmação do estado original.
3. Visão pontual e intervalos semiabertos `[valid_from, valid_to)`.
4. Janela por interseção (`any`) e cobertura integral (`all`).
5. Composição de camada e filtro de propriedades num subgrafo induzido.
6. Menor chegada com espera: dois saltos até a UTI, chegada às 08:15 UTC.
7. BFS temporal com menos saltos: um salto, chegada às 08:21 UTC.
8. Correção retroativa de validade: chegada atual às 08:07 UTC; consulta
   no watermark antigo continua chegando às 08:15 UTC.
9. Exclusão e alteração de paciente com preservação das propriedades antigas.
10. Arrow IPC lido por lotes via HTTP autenticado em Python.
11. Eventos auditáveis e GraphRAG com documento, vetor e caminhos de evidência.
12. Grau calculado sobre a projeção temporal reutilizável.

`report.json` contém as verificações e respostas completas.
`simulated_data.json` registra a topologia simulada original.
`server.log` e o data root pertencem apenas ao processo criado pelo programa.
A visualização usa esses intervalos; suas mudanças no slider são locais,
enquanto as verificações do relatório foram executadas contra o banco.

## Contratos e limites

Os horários de validade são simulados, em UTC. O tempo de conhecimento é o
watermark real retornado pelo journal; não é inventado a partir do relógio
Python. A correção altera a validade, sem sobrescrever estados históricos.

O envelope HTTP devolve as linhas dos procedimentos. Para este conjunto,
sem loops, o programa calcula a quantidade de relações na projeção como
metade da soma dos graus não dirigidos. Essa fórmula não é uma contagem
genérica para grafos com loops.

O programa inicia e termina somente seu próprio servidor, numa porta livre,
com credenciais aleatórias e diretório novo. Não conecta ao serviço instalado,
não utiliza dados existentes e não publica nada. Os dados são sintéticos;
nomes de pacientes não correspondem a pessoas reais.

GraphRAG entrega evidências estruturais, sem LLM ou alegação de causalidade.
CPU local; não demonstra GPU, escala distribuída ou desempenho NVMe.
