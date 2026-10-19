# Hospital longitudinal pelo MCP nativo

Esta versão consulta diretamente `POST /mcp` do NexusDB. O Python negocia
`initialize`, envia `notifications/initialized`, descobre `tools/list` e executa
`tools/call`. A LLM é opcional e recebe somente documentos retornados pelo MCP.

Fluxo: preparação administrativa HTTP → banco isolado → cliente MCP → BFS nativo
→ documentos e proveniência → explicação opcional pelo Gemma local.

## Executar

Requer Python padrão e `E:\nexusdb\target\debug\nexusdb.exe` com MCP nativo.
Não requer instalar SDK MCP. Cada execução cria diretório e processo próprios,
porta livre, credenciais aleatórias e banco `EXAMPLE_HOSPITAL_MCP_P001`.
Não acessa o serviço instalado. Encerra somente o processo criado pelo exemplo.

Sem modelo, compatível com CMD e PowerShell:

```bat
python E:\nexusdb\examples\hospital_longitudinal-Example\demo_mcp.py --create-lab
```

Com seu Gemma local:

```bat
python E:\nexusdb\examples\hospital_longitudinal-Example\demo_mcp.py --create-lab --gguf "F:\Jarvis\modelos_locais\gemma-3-1b-it-Q4_K_M.gguf" --gguf-python "F:\WinPython\python\python.exe" --llm-max-tokens 1024
```

O Python padrão executa HTTP; WinPython executa apenas inferência em subprocesso,
sem receber as credenciais do banco. O modelo não escolhe ferramentas, não recebe
permissão de escrita e não executa ações. A saída precisa de revisão humana.

O relatório fica em `E:\nexusdb\target\hospital-mcp\run-...\report.json`.
Inclui ferramentas descobertas, evidência MCP, métodos/status/tempos sem senhas,
motivo de encerramento, truncamento e `generation.validation`.
`status: passed` valida os checks da integração, inclusive o bloqueio de saídas
inválidas. Para saber se uma resposta foi aceita, consulte
`generation.validation.accepted` e `generation.answer_presented`.

## Saída estruturada e bloqueio de divergências

A LLM deve retornar somente `{"atendimentos": [...]}`, sem prosa ou markdown.
O worker compila o esquema com `LlamaGrammar.from_json_schema` e passa a gramática
ao `create_chat_completion`. A restrição atua durante a amostragem dos tokens,
não apenas no prompt. Se a compilação falhar, a execução falha explicitamente;
não há fallback para geração livre. Outros exemplos GGUF continuam livres quando
não fornecem esquema. O relatório registra `generation_schema` e
`generation.output_constraint: json_schema_grammar`.

O esquema exige os campos, seus tipos, três atendimentos e dois IDs OBS por
atendimento; proíbe propriedades extras. Os valores factuais não são fixados na
gramática: datas, recursos e fontes continuam sendo conferidos pelo validador
contra o MCP. Mesmo com gramática, esgotar tokens pode produzir JSON incompleto,
que permanece bloqueado. O limite padrão desta versão é 1024 tokens.

Cada atendimento exige exatamente `atendimento`, `entrada`, `saida`, `liberacao`,
`recurso`, `fonte`, `versao` e `observacoes` (os dois IDs OBS).

O validador obtém os valores esperados dos nós estruturados retornados no próprio
BFS MCP: Internacao, Observacao, Fonte e Documento. Não usa o gabarito da fixture.
Confere correspondência exata por atendimento e exige cobertura completa, sem
duplicatas, campos extras, fontes antigas ou fatos inventados. Confusão entre
saída e liberação, troca de datas e JSON incompleto são recusados. A ordem dos
atendimentos e dos IDs OBS pode variar. Datas devem manter o formato UTC original.
Inconsistência entre a internação e a observação de higienização impede a geração.

Somente registros aprovados são formatados deterministicamente para exibição.
Em caso de rejeição, a aplicação mostra apenas um código como
`EVIDENCE_MISMATCH_LIBERACAO`, `INVALID_JSON` ou `OUTPUT_TRUNCATED`.
Não exibe nem grava a saída bruta divergente; registra somente seu SHA-256,
metadados e motivo. Não completa a resposta automaticamente e não faz novas
tentativas silenciosas. Aumentar tokens pode evitar truncamento, mas não garante
resposta válida.

Essa aprovação significa igualdade dos campos com a evidência recuperada;
não valida a verdade dos dados de origem nem a segurança clínica. Por isso
`factual_accuracy_validated` permanece `false` e a revisão permanece necessária.

## Dados e segurança

Reutiliza a fixture autoral do hospital, publicando apenas P001: três atendimentos,
seis observações e três documentos com fonte/versão, além de internações, leito,
quarto e unidade. O gabarito fica separado em disco e não é enviado ao modelo ou
ao banco. Os IDs nativos iniciais vêm da ingestão, sem consulta HTTP auxiliar para
preencher a resposta MCP.

O catálogo permite somente `nexus_schema`, `nexus_graph_stats`, `nexus_bfs` e
`nexus_neighbors` ao usuário `hospital_reader`, que recebe READ nesse banco.
Os testes verificam descoberta, conteúdo recuperado, recusa de truncamento,
recusa de escrita e revogação de READ durante uma sessão MCP aberta.

**A fronteira de autorização é o banco completo contendo P001.** As ferramentas
atuais de grafo não equivalem à ACL de documentos do Knowledge. Não publique um
banco com vários pacientes a um leitor que deva acessar apenas um deles usando
este desenho. Não desative a política scoped do exemplo `demo.py` para adaptá-lo.

## Diferenças do exemplo HTTP

| Aspecto | `demo.py` | `demo_mcp.py` |
|---|---|---|
| Recuperação | Knowledge pela API HTTP | BFS por MCP nativo |
| Autorização demonstrada | Por documento/contexto | READ por banco com um paciente |
| Busca híbrida lexical/vetor/PPR | Sim | Não |
| Correção e consulta histórica | Sim | Não |
| Geração GGUF opcional | Sim | Sim |

O MCP atual não anuncia `knowledge.hybridSearch` ou `knowledge.contextPack`.
Esta versão demonstra recuperação por relações, sem prometer equivalência à
busca híbrida. BFS é não direcionado; caminhos estruturais não provam causalidade.
Não há diagnóstico, recomendação clínica ou validação médica.

Inspiração metodológica: Park, Chen e Dettmers,
*Synthetic Hospital: An Open, Verifiable, Physician-Validated Longitudinal EHR
Benchmark*, [arXiv:2609.30027v1](https://arxiv.org/abs/2609.30027).
Os dados e resultados clínicos do artigo não foram importados; isto não reproduz
seu benchmark. Consulte também [o exemplo principal](README.md).

Testes locais:

```bat
cd E:\nexusdb\examples\hospital_longitudinal-Example
python -m unittest test_mcp.py test_structured_response.py
```
