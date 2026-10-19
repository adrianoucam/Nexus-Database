# Validação do hospital longitudinal

## Versão MCP nativa

### Geração restringida por esquema JSON

Executada com o Gemma local, llama-cpp-python instalado e worker WinPython:
**12 verificações integradas passaram** e a resposta dos três atendimentos foi
aceita com `EXACT_MATCH_TO_MCP_EVIDENCE`. Entrada, saída, liberação, recurso,
fonte, versão e dois IDs OBS por atendimento coincidiram com os nós MCP.
[Relatório com geração restringida](../../target/hospital-mcp/run-1792426227395456300/report.json).

O esquema foi compilado explicitamente por `LlamaGrammar.from_json_schema` e
passado ao gerador, sem fallback livre. Os **23 testes unitários passaram**:
18 do hospital e cinco do worker, incluindo transporte do esquema ao subprocesso,
passagem da gramática ao modelo e falha de compilação sem executar geração livre.
Essa rodada demonstra correspondência com dados sintéticos recuperados, sem
validação clínica nem garantia de aprovação em toda execução futura.

### Validação estruturada após geração

O ajuste de bloqueio foi executado com o Gemma local e o worker WinPython:
**12 verificações integradas passaram**. A saída atingiu 512 tokens e foi
recusada com `OUTPUT_TRUNCATED`, sem apresentar ou salvar o texto bruto gerado.
`generation.answer_presented` ficou `false`; isto valida a rejeição segura,
não uma geração aprovada. [Relatório dessa execução](../../target/hospital-mcp/run-1792419676109156000/report.json).

**18 testes unitários passaram** (`test_dataset.py`, `test_mcp.py`,
`test_structured_response.py`), incluindo aprovação de JSON correto, divergências
em cada campo, erros observados na resposta anterior do Gemma, duplicação,
omissão, prosa extra, JSON inválido, truncamento e inconsistência da evidência.
Os valores esperados são construídos dos nós MCP, sem usar gabarito na validação
da resposta. Saídas aceitas usam apresentação determinística dos campos.

### Primeira versão

Em 19/10/2026, `demo_mcp.py --create-lab` passou **9 verificações integradas**
em processo NexusDB isolado. O relatório contém a negociação, catálogo e
evidências recuperadas exclusivamente por `tools/call`, incluindo três documentos
e seis fatos. Truncamento, escrita não publicada e revogação READ foram testados.
O banco contém somente P001; isto testa autorização por banco, sem ACL documental.

[Relatório MCP aprovado](../../target/hospital-mcp/run-1792419284090958900/report.json).
Os **11 testes unitários** de `test_dataset.py` e `test_mcp.py` passaram juntos.
A geração GGUF dessa versão MCP não foi executada nesta rodada. Os primeiros
ensaios expuseram profundidade insuficiente para alcançar a unidade e DELETE da
sessão recusado após revogação; o exemplo agora percorre cinco níveis e trata
somente esse HTTP 403 esperado no encerramento, sempre parando seu processo.

## Versão HTTP Knowledge

Executada em 19/10/2026 no NexusDB real, por HTTP e em instância isolada.

- **21 verificações integradas passaram**, incluindo vinte tarefas de recuperação, fatos estruturados, ACL, proveniência, correção temporal e revogação.
- **9 testes unitários passaram**, incluindo fixture determinística, integridade e detecção de citações obsoletas.
- Carga inicial confirmada: **406 nós e 605 relações**, com 20 pacientes, 60 atendimentos, 120 observações e 60 documentos.
- Geração de arquivos sem servidor também foi executada com `--generate-only`.
- A geração opcional GGUF **não foi executada nesta rodada**. Os resultados não medem qualidade clínica, semântica geral, escala ou GPU.

[Relatório completo](../../target/hospital-longitudinal/run-1792417165308156800/report.json) · [Log da rodada aprovada](../../target/hospital-longitudinal-verified.log).

Os relatórios de rodadas preliminares também foram preservados. Elas identificaram diferenças de envelope de `graph.historyStatus` e o contrato de `memory.supersede`; o exemplo foi ajustado aos contratos reais e executado novamente.

As métricas de recuperação perfeitas pertencem à fixture controlada e à busca pelo identificador do paciente. Não equivalem a desempenho clínico ou a reprodução dos resultados de Synthetic Hospital.

```powershell
Set-Location E:\nexusdb
python -m unittest discover -s examples/hospital_longitudinal-Example -p test_dataset.py -v
python examples/hospital_longitudinal-Example/demo.py --create-lab
```
