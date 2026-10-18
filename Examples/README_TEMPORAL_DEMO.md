# Teste com hospital simulado

No checkout do NexusDB, com Rust/Cargo e as dependências disponíveis:

```powershell
cd E:/nexusdb
cargo run --offline --example temporal_hospital_demo -- --patients 1000 --seed 42 --output E:/nexusDB-tests/temporal-demo-output
```

Se ainda não houver dependências no cache, execute sem `--offline` para obtê-las.
O programa cria um diretório novo por execução, lança apenas seu próprio
processo, usa uma senha efêmera, habilita CPU nesse processo e histórico
somente no database `EXAMPLE_TEMPORAL_HOSPITAL`.
Não usa o serviço instalado nem bancos existentes. Não altera visibilidade
de repositórios. Não exige Python, GPU, API de LLM ou dados reais.

O padrão é 250 pacientes; `--patients` aceita 2 a 10000. Com 1000 pacientes,
são 2004 nós e 2005 relações. `--seed` torna os dados reproduzíveis.
Os embeddings são sintéticos, para testar recuperação, não qualidade semântica.

O cenário inclui setores, pacientes, documentos e transferências cujos
horários distinguem caminho estrutural, menor quantidade de saltos e menor
tempo de chegada. Depois aplica uma correção retroativa e exclui um paciente.

As 15 verificações cobrem chegada mínima, BFS cronológico, rejeição de ordem
temporal inválida, janelas `any`/`all`, busca vetorial e evidências, correção
retroativa, versões antes/depois, exclusão histórica, lista de eventos, cache,
backup SQLite completo, BFS em disco e recarga. Falha encerra com código não
zero; sucesso imprime `PASS`.

Cada execução preserva:

- `simulated_hospital.json`: os dados de entrada.
- `report.json`: resultados das verificações, consultas de exemplo,
  ambiente e duração total.
- `data`: o banco isolado com journal e snapshot CSR.

A duração relatada é de validação, não um benchmark comparativo. Consulte
[semântica e limites](../Docs/TEMPORAL_ENGINE.md) antes de habilitar em uma
instalação existente.
