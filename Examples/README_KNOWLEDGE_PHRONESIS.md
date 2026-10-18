# Demonstração Cortex/Phronesis

Objetivo: testar contratos de conhecimento, memória, busca híbrida, argumentação, deliberação e proveniência com dados simulados no servidor real, usando somente Python padrão e NexusDB.

```powershell
cd E:\nexusdb
cargo build --features phronesis,datalog,embedded,spatial-geoparquet --bins
py examples/knowledge_phronesis_demo.py --output knowledge-python-output
```

Cada execução cria uma pasta run distinta, credenciais aleatórias e servidor/database isolados. O teste termina com a contagem de verificações e caminho de report.json. Não usa nem altera os bancos do serviço instalado. O relatório contém resultados MCDA, replay, PPR e duração por chamada sem credenciais. Revisão/aprovação são simuladas; nenhuma ação externa é executada.

[Contratos, procedimentos e limitações](../Docs/KNOWLEDGE_PHRONESIS.md). [Interface espacial em Tkinter](../Docs/SPATIAL_INTEGRATION.md). Testes Rust incluem Datalog recursivo/negação, embedded sem HTTP e regressões dos módulos existentes. Licença igual à [raiz](../LICENSE).
