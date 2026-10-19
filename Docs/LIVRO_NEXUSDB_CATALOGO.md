# NexusDB na prática — catálogo de programas

Companheiro de [NexusDB na prática](LIVRO_NEXUSDB.md). Edição de 18/10/2026.

Inventário estático de **203 arquivos autorais** de exemplos, auxiliares, testes e protótipos. As opções foram extraídas do AST, sem importar módulos ou iniciar aplicações. Não são uma lista de comandos que deva ser executada inteira.

O manifesto [JSON](tools/book_inventory.json) registra linhas e SHA-256 para rastrear a edição das fontes. O script [build_book_catalog.py](tools/build_book_catalog.py) regenera este catálogo nos checkouts irmãos.

Pastas de relatórios, binários, dependências instaladas, ambientes virtuais e exports gerados foram excluídos. Documentos, requisitos e datasets são citados nos roteiros do livro; não entram na contagem de programas.

| Família | Arquivos |
|---|---:|
| Exemplos do servidor | 113 |
| Exemplos NPL | 3 |
| Cliente de terminal | 3 |
| Experimentos Rust legados | 1 |
| Coleção externa: Agent-Examples | 5 |
| Coleção externa: Agent-Scope | 3 |
| Coleção externa: BioGrid | 8 |
| Coleção externa: BMSSP-Dijkstra | 5 |
| Coleção externa: FolhaPagto-Example | 11 |
| Coleção externa: geospatial-urban-graph | 4 |
| Coleção externa: GraphRag | 1 |
| Coleção externa: GraphRag2 | 2 |
| Coleção externa: nexusdb-AI | 8 |
| Coleção externa: Openfights | 6 |
| Coleção externa: phorenesis | 1 |
| Coleção externa: SuplyChain-Ford-Kaggle | 8 |
| Coleção externa: nexusdb_python_tests | 8 |
| Protótipos de referência: extensão de grafo | 3 |
| Protótipos de referência: espacial | 10 |

## Como ler cada ficha

Uma descrição extraída de docstring reflete o comentário da fonte, que pode ser histórico. Para estado atual e limitações, prevalecem os capítulos do livro e os contratos verificados do servidor. Funções/classes ajudam a localizar implementações; sua presença não demonstra que todas as rotas estejam integradas.

## Exemplos do servidor

### [examples/Advanced-Examples/nexusdb_mga/demo.py](examples/Advanced-Examples/nexusdb_mga/demo.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Illustrated, reproducible multivariate graph benchmark. See --help.

Opções encontradas: `--nodes`, `--nexus-json`, `--features`, `--n`, `--k`, `--seed`, `--output`.

Funções/classes: `generate_hospital`, `plot_scatter`, `main`.

### [examples/Advanced-Examples/nexusdb_mga/demo_v02.py](examples/Advanced-Examples/nexusdb_mga/demo_v02.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Additional scientific demo; retains demo.py v0.1 unchanged.

Opções encontradas: `--n`, `--k`, `--seed`, `--nodes`, `--features`, `--output`.

Funções/classes: `main`.

### [examples/Advanced-Examples/nexusdb_mga/demo_v03.py](examples/Advanced-Examples/nexusdb_mga/demo_v03.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Run reproducible, actual kNN+Louvain benchmarks on simulated or exported NexusDB data.

Opções encontradas: `--nodes`, `--features`, `--label-column`, `--n`, `--k`, `--repeats`, `--fraction`, `--seed`, `--bootstrap`, `--output`.

Funções/classes: `main`.

### [examples/Advanced-Examples/nexusdb_mga/demo_v04.py](examples/Advanced-Examples/nexusdb_mga/demo_v04.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: v0.4: reproducible independent-dataset robustness study.

Opções encontradas: `--datasets`, `--n`, `--dimensions`, `--k`, `--bootstrap`, `--seed`, `--output`.

Funções/classes: `main`.

### [examples/Advanced-Examples/nexusdb_mga/demo_v05.py](examples/Advanced-Examples/nexusdb_mga/demo_v05.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Scientific robustness demonstration, synthetic data only; no database writes.

Opções encontradas: `--datasets`, `--n`, `--dimensions`, `--k`, `--strength`, `--seed`, `--output`.

Funções/classes: `main`.

### [examples/Advanced-Examples/nexusdb_mga/demo_v06.py](examples/Advanced-Examples/nexusdb_mga/demo_v06.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: v0.6 reproducible benchmark demo. Use --quick for smoke test.

Opções encontradas: `--datasets`, `--n`, `--dimensions`, `--sizes`, `--k`, `--repeats`, `--bootstrap`, `--seed`, `--output`, `--skip-scalability`, `--quick`.

Funções/classes: `main`.

### [examples/Advanced-Examples/nexusdb_mga/demo_v07.py](examples/Advanced-Examples/nexusdb_mga/demo_v07.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Read-only, opt-in HTTP benchmark against an explicitly configured NexusDB API.

Opções encontradas: `--contract`, `--backends`, `--nodes`, `--degree`, `--seed`, `--repeats`, `--warmups`, `--tolerance`, `--output`.

Funções/classes: `main`.

### [examples/Advanced-Examples/nexusdb_mga/demo_v08.py](examples/Advanced-Examples/nexusdb_mga/demo_v08.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Offline reproducible dataset-manager demonstration.

Opções encontradas: `--output`, `--nodes`, `--seed`.

Funções/classes: `main`.

### [examples/Advanced-Examples/nexusdb_mga/demo_v09.py](examples/Advanced-Examples/nexusdb_mga/demo_v09.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Offline v0.9 demonstration: academic-style fixtures and property roundtrips.

Opções encontradas: `--output`.

Funções/classes: `main`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/__init__.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/__init__.py)

Inicialização/exportações do pacote; não executar isoladamente.

Descrição na fonte: NexusDB MGA: multivariate graph analytics without modifying the database core.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/academic_importers.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/academic_importers.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Local academic dataset readers. No implicit downloads or pickle execution.

Funções/classes: `_open_text`, `_provenance`, `read_snap_edgelist`, `read_planetoid`, `read_matrix_market`, `import_academic_dataset`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/adapters.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/adapters.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Read-only interchange adapters. No assumptions about NexusDB wire protocol.

Funções/classes: `read_nodes`, `read_edges`, `read_nexusdb_json`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/advanced_benchmarks.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/advanced_benchmarks.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: v0.6 additive scientific benchmarks; independent datasets are inference units.

Funções/classes: `_communities`, `perturbation_confidence`, `independent_classifier_benchmark`, `_run_isolated_worker`, `isolated_scalability_benchmark`, `export_v06`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/analytics.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/analytics.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Statistical operations and graph creation, all in-memory and non-invasive.

Funções/classes: `prepare_features`, `correlation_matrix`, `distance_matrix`, `build_knn_graph`, `reduce_pca`, `factor_analysis`, `cluster_features`, `detect_anomalies`, `pagerank`, `graph_metrics`, `compare_graphs`, `correspondence_analysis`, `graph_to_tables`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/benchmark.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/benchmark.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: v0.3: paired, reproducible real algorithm executions (not fabricated measurements).

Funções/classes: `_bootstrap_ci`, `run_benchmark`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/datasets.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/datasets.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Reproducible graph dataset store: verified acquisition, CSV/JSON/CSR, provenance.

Funções/classes: `sha256`, `_atomic_write`, `_json`, `_node_id`, `validate_graph`, `_attributes`, `_property_payload`, `property_hash`, `_canonical`, `graph_hash`, `_export`, `_import`, `DatasetManager`, `synthetic_graph`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/diagnostics.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/diagnostics.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Descriptive diagnostics for numeric datasets and graph degree inequality.

Funções/classes: `gini`, `lorenz`, `diagnose_features`, `association_report`, `covariance_diagnostics`, `degree_inequality`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/isolated_worker.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/isolated_worker.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Isolated process worker, invoked via python -m; never import in main benchmark.

Funções/classes: `main`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/learning.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/learning.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Supervised baseline and text-to-graph conversion.

Funções/classes: `classify_logistic_cv`, `text_similarity_graph`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/nexus_benchmark.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/nexus_benchmark.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: External, read-only NexusDB benchmark contract (v0.7).

Funções/classes: `HTTPContract`, `make_graph`, `graph_payload`, `run_python`, `_fetch_json`, `run_remote`, `score_difference`, `benchmark`, `export_results`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/optimization.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/optimization.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Constrained optimization and leakage-safe graph tuning.

Funções/classes: `optimize_allocation`, `tune_graph`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/perturbations.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/perturbations.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Deterministic stress transformations and mathematical invariance checks.

Funções/classes: `perturb_features`, `invariance_report`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/robustness.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/robustness.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Independent-dataset robustness experiments; additive v0.4 API.

Funções/classes: `make_independent_datasets`, `_rss_monitor`, `_holm`, `run_robustness_benchmark`, `save_robustness_results`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/scientific.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/scientific.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Independent-dataset stress study, community stability and scientific export.

Funções/classes: `_communities`, `stress_benchmark`, `export_scientific_report`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/statistics.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/statistics.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Robust descriptive statistics and paired inference.

Funções/classes: `descriptive_report`, `iqr_outliers`, `paired_comparison`.

### [examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/validation.py](examples/Advanced-Examples/nexusdb_mga/nexusdb_mga/validation.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Leakage-safe supervised baseline and classification metrics.

Funções/classes: `evaluate_classifiers`.

### [examples/Advanced-Examples/nexusdb_mga/tests/test_analytics.py](examples/Advanced-Examples/nexusdb_mga/tests/test_analytics.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `test_preparation`, `test_knn`, `test_mahalanobis_distance`, `test_pca_factors`, `test_clusters_anomalies`, `test_graph_metrics`, `test_correspondence`.

### [examples/Advanced-Examples/nexusdb_mga/tests/test_v02.py](examples/Advanced-Examples/nexusdb_mga/tests/test_v02.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `test_stats`, `test_paired`, `test_allocation`, `test_graph_tuning`, `test_text_graph`, `test_cv`, `test_legacy_exports`.

### [examples/Advanced-Examples/nexusdb_mga/tests/test_v03.py](examples/Advanced-Examples/nexusdb_mga/tests/test_v03.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `fixture`, `test_repetitions_and_pairs`, `test_unlabeled_and_old_api`, `test_invalid_inputs`.

### [examples/Advanced-Examples/nexusdb_mga/tests/test_v04.py](examples/Advanced-Examples/nexusdb_mga/tests/test_v04.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `test_independent_seeds`, `test_robustness_outputs`.

### [examples/Advanced-Examples/nexusdb_mga/tests/test_v05.py](examples/Advanced-Examples/nexusdb_mga/tests/test_v05.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `test_gini_lorenz`, `test_diagnostics`, `test_invariance`, `test_perturbations`, `test_validation`, `test_stress`.

### [examples/Advanced-Examples/nexusdb_mga/tests/test_v06.py](examples/Advanced-Examples/nexusdb_mga/tests/test_v06.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `test_perturbation_ci`, `test_classifiers_independent`, `test_scalability_isolated`.

### [examples/Advanced-Examples/nexusdb_mga/tests/test_v07.py](examples/Advanced-Examples/nexusdb_mga/tests/test_v07.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `Handler`, `server`, `test_python_baseline`, `test_remote_confirmed_and_cuda_fallback`, `test_unavailable_without_contract`, `test_node_validation`, `test_export`.

### [examples/Advanced-Examples/nexusdb_mga/tests/test_v08.py](examples/Advanced-Examples/nexusdb_mga/tests/test_v08.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `test_roundtrip_all_formats`, `test_directed_and_isolates`, `test_tamper_detected`, `test_invalid_graph`, `test_overwrite`, `test_download_hash_and_provenance`, `test_bad_csr_detected_without_hash`.

### [examples/Advanced-Examples/nexusdb_mga/tests/test_v09.py](examples/Advanced-Examples/nexusdb_mga/tests/test_v09.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `test_properties_all_formats`, `test_tampered_properties`, `test_snap`, `test_planetoid`, `test_matrix_market`, `test_legacy_without_properties`.

### [examples/academico_api_ia-Example/01_chaves_api.py](examples/academico_api_ia-Example/01_chaves_api.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Biblioteca acadêmica: chave de endpoint, parâmetros, isolamento e revogação.

Funções/classes: `main`.

### [examples/academico_api_ia-Example/02_npl_academico.py](examples/academico_api_ia-Example/02_npl_academico.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: NPL acadêmica: regras explícitas, CALL, leitura tipada e permissão por rotina.

Funções/classes: `main`.

### [examples/academico_api_ia-Example/03_ia_graphrag.py](examples/academico_api_ia-Example/03_ia_graphrag.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Projeto acadêmico: RAG/GraphRAG por fatia publicada e comparação nativa real.

Funções/classes: `expand`, `main`.

### [examples/academico_api_ia-Example/04_conhecimento_api.py](examples/academico_api_ia-Example/04_conhecimento_api.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Recuperação híbrida nativa com API key, ACL, vetores e relevância de grafo.

Funções/classes: `main`.

### [examples/academico_api_ia-Example/cliente_chave.py](examples/academico_api_ia-Example/cliente_chave.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Cliente para endpoint existente. Senha/chave nunca são argumentos do processo.

Opções encontradas: `--url`, `--endpoint`, `--params`.

Funções/classes: `main`.

### [examples/academico_api_ia-Example/common.py](examples/academico_api_ia-Example/common.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Infraestrutura de laboratório isolado; nenhuma chave é gravada no relatório.

Opções encontradas: `--server`, `--gateway`, `--output`, `--ollama-model`, `--gguf`, `--gguf-python`, `--llm-context`, `--llm-max-tokens`.

Funções/classes: `options`, `Lab`.

### [examples/academico_api_ia-Example/executar_todos.py](examples/academico_api_ia-Example/executar_todos.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Executa os quatro laboratórios em processos separados e preserva o resultado.

Funções/classes: `main`.

### [examples/academico_api_ia-Example/local_gguf.py](examples/academico_api_ia-Example/local_gguf.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Inferência GGUF direta no processo; nenhum download ou servidor de modelos.

Funções/classes: `generate`, `generate_external`.

### [examples/academico_api_ia-Example/test_local_gguf.py](examples/academico_api_ia-Example/test_local_gguf.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Descrição na fonte: Testes do isolamento do worker; não carregam pesos nem acessam o banco.

Funções/classes: `WorkerTests`.

### [examples/agent-tools-Example/benchmark.py](examples/agent-tools-Example/benchmark.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Compare native vs Agent executor using separate temporary databases/processes.

Funções/classes: `memory_reader`, `main`.

### [examples/agent-tools-Example/client.py](examples/agent-tools-Example/client.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Read-only Agent Tools client; standard library, no stored credentials.

Opções encontradas: `--url`, `--user`, `--database`, `--tool`, `--input`.

### [examples/agent_tools_bench.rs](examples/agent_tools_bench.rs)

Exemplo Rust; use o alvo Cargo correspondente, quando disponível.

Funções/classes: `main`.

### [examples/arrow_client.py](examples/arrow_client.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Authenticated Arrow streaming client. No server file-system access is needed.

Funções/classes: `export_properties`, `batches`.

### [examples/authentication_test.py](examples/authentication_test.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Testa a autenticação atual, sem escrever dados ou imprimir credenciais.

Funções/classes: `main`.

### [examples/calibrate_compute.rs](examples/calibrate_compute.rs)

Exemplo Rust; use o alvo Cargo correspondente, quando disponível.

Funções/classes: `main`.

### [examples/crud_academico-Example/app.py](examples/crud_academico-Example/app.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: CRUD acadêmico real no NexusDB. Python 3.10+, somente biblioteca padrão.

Opções encontradas: `--url`, `--user`, `--database`, `--create`, `--port`, `--no-browser`.

Funções/classes: `Client`, `make_server`, `main`.

### [examples/crud_academico-Example/index.html](examples/crud_academico-Example/index.html)

Interface da aplicação; o backend correspondente controla os dados.

### [examples/crud_academico-Example/optimization.py](examples/crud_academico-Example/optimization.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Otimização multiobjetivo e análise de recursos para a demo escolar NexusDB.

Funções/classes: `_truthy`, `OptimizationSchool`, `compare_profiles`.

### [examples/crud_academico-Example/planning.py](examples/crud_academico-Example/planning.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Restrições de horários e planejamento por GRASP + busca local; sem dependências externas.

Funções/classes: `number`, `minutes`, `clock`, `availability_for_turn`, `windows`, `available`, `overlap`, `School`, `node_properties`.

### [examples/crud_academico-Example/test_integration.py](examples/crud_academico-Example/test_integration.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Descrição na fonte: Teste real isolado: python test_integration.py --server ../../target/release/nexusdb.exe

Opções encontradas: `--server`.

Funções/classes: `run`.

### [examples/crud_academico-Example/test_planning.py](examples/crud_academico-Example/test_planning.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `fixture`, `PlanningTests`.

### [examples/crypto_temporal_lab.py](examples/crypto_temporal_lab.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Laboratório didático: Python padrão + APIs reais do NexusDB.

Opções encontradas: `--server`, `--output`, `--seed`, `--scenario`, `--csv`, `--headless`, `--gui-smoke`.

Funções/classes: `utc`, `synthetic`, `write_csv`, `read_csv`, `cosine_sync`, `metrics`, `NexusSession`, `Lab`, `money`, `gui`, `main`.

### [examples/example_packages.py](examples/example_packages.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Load the AI example under its Python name from the renamed disk folder.

Funções/classes: `load_ai_example`.

### [examples/graphrag_orders-Example/demo.py](examples/graphrag_orders-Example/demo.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Demo reproduzivel: atendimento de pedidos com HNSW + GraphRAG. Apenas stdlib.

Opções encontradas: `--url`, `--user`, `--database`, `--order`, `--output`, `--generate-only`.

Funções/classes: `dataset`, `tokens`, `Tfidf`, `Client`, `upload`, `measured`, `evaluate`, `report_html`, `main`.

### [examples/hospital_longitudinal-Example/dataset.py](examples/hospital_longitudinal-Example/dataset.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Fixture autoral determinística; não reproduz pacientes nem dados do artigo.

Funções/classes: `iso`, `timestamp`, `build`, `validate`.

### [examples/hospital_longitudinal-Example/demo.py](examples/hospital_longitudinal-Example/demo.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Hospital longitudinal sintético no NexusDB: proveniência, ACL e histórico real.

Opções encontradas: `--generate-only`, `--create-lab`, `--server`, `--output`, `--seed`, `--gguf`, `--gguf-python`.

Funções/classes: `Demo`, `main`.

### [examples/hospital_longitudinal-Example/demo_mcp.py](examples/hospital_longitudinal-Example/demo_mcp.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Hospital sintético: recuperação pelo MCP nativo e explicação GGUF opcional.

Opções encontradas: `--create-lab`, `--server`, `--output`, `--gguf`, `--gguf-python`, `--llm-max-tokens`.

Funções/classes: `patient_slice`, `evidence_rows`, `main`.

### [examples/hospital_longitudinal-Example/evaluation.py](examples/hospital_longitudinal-Example/evaluation.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Avaliação de IDs estruturados; não é um avaliador clínico de texto livre.

Funções/classes: `metrics`, `answer_from_rows`, `evaluate_generated`.

### [examples/hospital_longitudinal-Example/structured_response.py](examples/hospital_longitudinal-Example/structured_response.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Validação exata contra fatos estruturados recuperados pelo MCP, sem gabarito.

Funções/classes: `response_schema`, `expected_records`, `validate_response`, `display_response`.

### [examples/hospital_longitudinal-Example/test_dataset.py](examples/hospital_longitudinal-Example/test_dataset.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Descrição na fonte: Testes de fixture, integridade e avaliação; sem servidor nem modelo.

Funções/classes: `DatasetTests`.

### [examples/hospital_longitudinal-Example/test_mcp.py](examples/hospital_longitudinal-Example/test_mcp.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `HospitalMcpTests`.

### [examples/hospital_longitudinal-Example/test_structured_response.py](examples/hospital_longitudinal-Example/test_structured_response.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `StructuredTests`.

### [examples/knowledge_mcp.py](examples/knowledge_mcp.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Optional read-only MCP stdio adapter to an authenticated NexusDB instance.

Funções/classes: `NoRedirect`, `Bridge`, `main`.

### [examples/knowledge_phronesis_demo.py](examples/knowledge_phronesis_demo.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Testes didáticos reais: Cortex/Phronesis sobre Python padrão + NexusDB.

Opções encontradas: `--server`, `--output`.

Funções/classes: `evaluation`, `memory`, `validate`, `main`.

### [examples/leitos_hospitais-Example/app.py](examples/leitos_hospitais-Example/app.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Painel local de leitos fictícios HSJA. Python 3.10+, sem dependências.

Opções encontradas: `--dataset`, `--port`, `--no-browser`.

Funções/classes: `Hospital`, `make_server`, `main`.

### [examples/leitos_hospitais-Example/benchmark.py](examples/leitos_hospitais-Example/benchmark.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Executar: python benchmark.py --output benchmark_resultado.json

Opções encontradas: `--dataset`, `--at`, `--iterations`, `--generations`, `--seed`, `--blocked`, `--output`.

Funções/classes: `positive`, `main`.

### [examples/leitos_hospitais-Example/gerar_hsja_simulado.py](examples/leitos_hospitais-Example/gerar_hsja_simulado.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Simulador integralmente ficticio para prototipos de grafos hospitalares. Apenas stdlib.

Funções/classes: `add`, `dt`, `randt`, `weighted`.

### [examples/leitos_hospitais-Example/index.html](examples/leitos_hospitais-Example/index.html)

Interface da aplicação; o backend correspondente controla os dados.

### [examples/leitos_hospitais-Example/optimization.py](examples/leitos_hospitais-Example/optimization.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Benchmark experimental HSJA: somente dados fictícios, Python stdlib, CPU.

Funções/classes: `load`, `snapshot`, `compatible`, `benefit`, `greedy`, `matching`, `min_cost`, `genetic`, `solve`, `audit`.

### [examples/leitos_hospitais-Example/test_app.py](examples/leitos_hospitais-Example/test_app.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `HospitalTests`.

### [examples/leitos_hospitais-Example/test_optimization.py](examples/leitos_hospitais-Example/test_optimization.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `request`, `bed`, `Tests`.

### [examples/mcp-Example/01_descobrir.py](examples/mcp-Example/01_descobrir.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Descobre ferramentas de um NexusDB existente; não cria nem modifica dados.

Opções encontradas: `--url`, `--user`, `--database`, `--stats`.

Funções/classes: `main`.

### [examples/mcp-Example/02_laboratorio.py](examples/mcp-Example/02_laboratorio.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Testes reais MCP: descoberta, grafo acadêmico, limites e revogação READ.

Opções encontradas: `--server`, `--output`.

Funções/classes: `main`.

### [examples/mcp-Example/03_assistente.py](examples/mcp-Example/03_assistente.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Consulta MCP com plano fixo e explicação opcional por LLM local.

Opções encontradas: `--server`, `--output`, `--tarefa`, `--gguf`, `--ollama-model`, `--gguf-python`, `--llm-max-tokens`.

Funções/classes: `main`.

### [examples/mcp-Example/client.py](examples/mcp-Example/client.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Cliente do subconjunto MCP HTTP NexusDB; sem redirects ou segredos em erros.

Funções/classes: `McpError`, `NoRedirect`, `Client`.

### [examples/mcp-Example/lab.py](examples/mcp-Example/lab.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Fixture acadêmica isolada para estudar descoberta, grafos e autorização MCP.

Funções/classes: `Lab`.

### [examples/mcp-Example/test_client.py](examples/mcp-Example/test_client.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Descrição na fonte: Testes locais de fronteira do cliente, sem acessar servidor.

Funções/classes: `ClientTests`.

### [examples/native_mcp_demo.py](examples/native_mcp_demo.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: MCP nativo: hospital sintético, cliente Python padrão e comparação com Agent API.

Opções encontradas: `--server`, `--output`, `--patients`, `--benchmark`, `--samples`, `--concurrency`.

Funções/classes: `MCPClient`, `percentiles`, `main`.

### [examples/nexusdb_ai-Example/__init__.py](examples/nexusdb_ai-Example/__init__.py)

Inicialização/exportações do pacote; não executar isoladamente.

### [examples/nexusdb_ai-Example/adapter.py](examples/nexusdb_ai-Example/adapter.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Explicit adapter contract for connecting to a real NexusDB deployment.

Funções/classes: `NexusDBAdapter`.

### [examples/nexusdb_ai-Example/core.py](examples/nexusdb_ai-Example/core.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: NexusDB AI v0.1: local retrieval, safe graph plans, and decision support.

Funções/classes: `tokens`, `cosine`, `Embedding`, `HashEmbedding`, `Ollama`, `Node`, `Edge`, `Graph`, `MemoryGraph`, `QueryPlan`, `execute_plan`, `parse_plan`, `plan_question`, `VectorIndex`, `build_index`, `retrieve`; mais 3 símbolos no manifesto.

### [examples/nexusdb_ai-Example/gateway_adapter.py](examples/nexusdb_ai-Example/gateway_adapter.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Adapter for the verified Rust gateway; all execution stays in NexusDB.

Funções/classes: `GatewayTransport`, `PublishedGatewayAdapter`.

### [examples/nexusdb_ai-Example/http_adapter.py](examples/nexusdb_ai-Example/http_adapter.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Contract-driven HTTP bridge. No assumptions about actual NexusDB routes.

Funções/classes: `ContractError`, `HttpContract`, `HttpTransport`, `NexusDBHttpAdapter`.

### [examples/nexusdb_oficina_comercial/comercial.py](examples/nexusdb_oficina_comercial/comercial.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: NexusDB Oficina Comercial: simulador interativo + adaptador nativo auditável.

Opções encontradas: `--mode`, `--host`, `--port`, `--nexus-url`, `--user`, `--password`, `--traversal-procedure`, `--snapshot`, `--gateway-url`, `--gateway-key`, `--mcda-endpoint`, `--traversal-endpoint`.

Funções/classes: `NativeError`, `NexusNative`, `GatewayNative`, `Workshop`, `serve`, `main`.

### [examples/nexusdb_oficina_comercial/dataset_base.py](examples/nexusdb_oficina_comercial/dataset_base.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Demo comercial NexusDB: oficina mecânica, grafo de recursos e MCDA auditável.

Opções encontradas: `--mode`, `--output`, `--base-url`, `--user`, `--password`, `--server`.

Funções/classes: `nodes_edges`, `bfs_path`, `priority`, `schedule`, `post`, `seed_live`, `save`, `main`.

### [examples/nexusdb_oficina_comercial/test_comercial.py](examples/nexusdb_oficina_comercial/test_comercial.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `TestCommercial`.

### [examples/oficina_mecanica_example/api_setup.py](examples/oficina_mecanica_example/api_setup.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Provisionamento explícito da oficina no NexusDB 7474 e perfis READ para gateway 8787.

Opções encontradas: `--output`, `--url`, `--existing-db`, `--report`, `--gateway-url`, `--ttl`.

Funções/classes: `post`, `check_gateway`, `native_headers`, `profiles`, `create_profiles`, `seed_live`, `seed_existing`, `issue_keys`, `main`.

### [examples/oficina_mecanica_example/app.py](examples/oficina_mecanica_example/app.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Painel explicável da oficina. Usa a v1 como motor e evita alegações de execução nativa não verificadas.

Opções encontradas: `--mode`, `--port`, `--history`, `--nexus-url`, `--user`, `--password`, `--traversal-procedure`, `--gateway-url`, `--gateway-key`, `--gateway-keys-file`, `--verify-gateway-data`, `--mcda-endpoint`, `--traversal-endpoint`.

Funções/classes: `WorkshopV2`, `serve`, `main`.

### [examples/oficina_mecanica_example/bootstrap_api_oficina.py](examples/oficina_mecanica_example/bootstrap_api_oficina.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Prepara apenas EXAMPLE_OFICINA_INTELIGENTE e inicia seu gateway separado.

Opções encontradas: `--check`.

Funções/classes: `private_json`, `health`, `main`.

### [examples/oficina_mecanica_example/comercial.py](examples/oficina_mecanica_example/comercial.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: NexusDB Oficina Comercial: simulador interativo + adaptador nativo auditável.

Opções encontradas: `--mode`, `--host`, `--port`, `--nexus-url`, `--user`, `--password`, `--traversal-procedure`, `--snapshot`, `--gateway-url`, `--gateway-key`, `--mcda-endpoint`, `--traversal-endpoint`.

Funções/classes: `NativeError`, `NexusNative`, `GatewayNative`, `Workshop`, `serve`, `main`.

### [examples/oficina_mecanica_example/dashboard.html](examples/oficina_mecanica_example/dashboard.html)

Interface da aplicação; o backend correspondente controla os dados.

### [examples/oficina_mecanica_example/dataset_base.py](examples/oficina_mecanica_example/dataset_base.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Demo comercial NexusDB: oficina mecânica, grafo de recursos e MCDA auditável.

Opções encontradas: `--mode`, `--output`, `--base-url`, `--user`, `--password`, `--server`.

Funções/classes: `nodes_edges`, `bfs_path`, `priority`, `schedule`, `post`, `seed_live`, `save`, `main`.

### [examples/oficina_mecanica_example/iniciar_api_oficina.bat](examples/oficina_mecanica_example/iniciar_api_oficina.bat)

Script operacional; leia efeitos e diretórios alvo antes de executar.

### [examples/oficina_mecanica_example/secure_store.py](examples/oficina_mecanica_example/secure_store.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Segredos locais protegidos por DPAPI CurrentUser; nunca imprime seu conteúdo.

Opções encontradas: `--output`, `--key-id`, `--ha`.

Funções/classes: `_crypt`, `restrict`, `save_json`, `load_json`, `migrate_json`, `main`.

### [examples/oficina_mecanica_example/seed_nexusdb.py](examples/oficina_mecanica_example/seed_nexusdb.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Carga explícita e verificável do grafo da oficina em NexusDB real.

Opções encontradas: `--repo`, `--server`, `--output`.

Funções/classes: `seed`.

### [examples/oficina_mecanica_example/test_api_setup.py](examples/oficina_mecanica_example/test_api_setup.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `TestAPISetup`.

### [examples/oficina_mecanica_example/test_secure_store.py](examples/oficina_mecanica_example/test_secure_store.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `SecureStoreTests`.

### [examples/oficina_mecanica_example/test_v2.py](examples/oficina_mecanica_example/test_v2.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `Tests`.

### [examples/password_security_validation.py](examples/password_security_validation.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Valida cofres DPAPI e recuperação numa instância descartável do NexusDB (Windows).

Opções encontradas: `--server`, `--output`.

Funções/classes: `main`.

### [examples/phase9_validation.py](examples/phase9_validation.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Out-of-core validation in a NEW data root; no production services or credentials.

Opções encontradas: `--binary`, `--server`, `--output`, `--nodes`, `--fanout`, `--history`.

Funções/classes: `main`.

### [examples/recovery-Example/demo.py](examples/recovery-Example/demo.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Mede perda de escritas HTTP após kill/restart de processos NexusDB próprios.

Opções encontradas: `--create-lab`, `--server`, `--output`, `--rounds`, `--rows`.

Funções/classes: `Instance`, `rows_for`, `scan`, `integrity`, `run_profile`, `main`.

### [examples/reset_admin_password.ps1](examples/reset_admin_password.ps1)

Script operacional; leia efeitos e diretórios alvo antes de executar.

### [examples/reset_admin_password.rs](examples/reset_admin_password.rs)

Exemplo Rust; use o alvo Cargo correspondente, quando disponível.

Funções/classes: `reset_admin`, `run`, `main`, `fixture`, `resets_locked_admin_without_touching_other_accounts_or_permissions`, `wrong_paths_short_passwords_and_inactive_admins_do_not_change_data`.

### [examples/rest_gateway_benchmark.py](examples/rest_gateway_benchmark.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: REST benchmark with generated representative graphs, isolated servers.

Opções encontradas: `--server`, `--gateway`, `--sizes`, `--samples`, `--concurrency`, `--output`, `--enable-gpu`.

Funções/classes: `rss`, `summary`, `main`.

### [examples/rest_gateway_validation.py](examples/rest_gateway_validation.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Valida gateway Axum e NexusDB reais, em processos/diretórios isolados.

Opções encontradas: `--server`, `--gateway`, `--output`.

Funções/classes: `main`.

### [examples/spatial_temporal_demo.py](examples/spatial_temporal_demo.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Demonstração isolada: Python padrão/Tkinter + funções nativas NexusDB.

Opções encontradas: `--server`, `--output`, `--headless`, `--smoke-gui`.

Funções/classes: `dataset`, `query`, `prepare`, `display`, `main`.

### [examples/temporal_graph_demo.py](examples/temporal_graph_demo.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Temporal graph demonstration inspired by the supplied Pometry proposal.

Opções encontradas: `--server`, `--output`, `--patients`, `--seed`.

Funções/classes: `main`, `render`.

### [examples/temporal_hospital_demo.rs](examples/temporal_hospital_demo.rs)

Exemplo Rust; use o alvo Cargo correspondente, quando disponível.

Funções/classes: `main`, `run`.

## Exemplos NPL

### [tools/npl_v015/examples/call_execute_cypher.json](tools/npl_v015/examples/call_execute_cypher.json)

Arquivo de instruções de demonstração; requer cliente/interpretador correspondente.

### [tools/npl_v015/examples/execute_inside.npl](tools/npl_v015/examples/execute_inside.npl)

Arquivo de instruções de demonstração; requer cliente/interpretador correspondente.

### [tools/npl_v015/examples/memory_limits.ps1](tools/npl_v015/examples/memory_limits.ps1)

Script operacional; leia efeitos e diretórios alvo antes de executar.

## Cliente de terminal

### [../nexusdb-cli/exemplos/admin.sql](../nexusdb-cli/exemplos/admin.sql)

Arquivo de instruções de demonstração; requer cliente/interpretador correspondente.

### [../nexusdb-cli/exemplos/exemplo.cypher](../nexusdb-cli/exemplos/exemplo.cypher)

Arquivo de instruções de demonstração; requer cliente/interpretador correspondente.

### [../nexusdb-cli/exemplos/exemplo.sql](../nexusdb-cli/exemplos/exemplo.sql)

Arquivo de instruções de demonstração; requer cliente/interpretador correspondente.

## Experimentos Rust legados

### [test_funcoes_rust/src/bin/test_ha_v22.rs](test_funcoes_rust/src/bin/test_ha_v22.rs)

Exemplo Rust; use o alvo Cargo correspondente, quando disponível.

Funções/classes: `execute`, `execute`, `execute`, `edge`, `run_execution_graph_cases`, `new`, `post`, `response_has_application_error`, `cluster_health`, `wait_for_leader`, `post_write`, `cypher`, `main`, `execution_graph_functional_suite`.

## Coleção externa: Agent-Examples

### [../nexusDB-tests/Agent-Examples/01_agent_tools_smoke.py](../nexusDB-tests/Agent-Examples/01_agent_tools_smoke.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Example 1 — Smoke test and analytics.

Opções encontradas: `--url`, `--user`, `--password`, `--database`, `--iterations`, `--limit`.

Funções/classes: `parse_args`, `main`.

### [../nexusDB-tests/Agent-Examples/02_graph_path_security_test.py](../nexusDB-tests/Agent-Examples/02_graph_path_security_test.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Example 2 — Graph path + validation/security regression checks.

Opções encontradas: `--url`, `--user`, `--password`, `--database`, `--source`, `--target`, `--directed`, `--mismatch-database`.

Funções/classes: `parse_args`, `check`, `main`.

### [../nexusDB-tests/Agent-Examples/03_vector_spatial_benchmark.py](../nexusDB-tests/Agent-Examples/03_vector_spatial_benchmark.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Example 3 — Vector + spatial benchmark.

Opções encontradas: `--url`, `--user`, `--password`, `--database`, `--index`, `--vector`, `--k`, `--ef`, `--x`, `--y`, `--radius`, `--label`, `--spatial-limit`, `--repeats`, `--csv`.

Funções/classes: `parse_vector`, `percentile`, `parse_args`, `run_benchmark`, `summarize`, `main`.

### [../nexusDB-tests/Agent-Examples/TESTES.BAT](../nexusDB-tests/Agent-Examples/TESTES.BAT)

Script operacional; leia efeitos e diretórios alvo antes de executar.

### [../nexusDB-tests/Agent-Examples/common.py](../nexusDB-tests/Agent-Examples/common.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Common helpers for NexusDB Agent Tool examples.

Funções/classes: `NexusConfig`, `NexusAgentClient`, `pretty`.

## Coleção externa: Agent-Scope

### [../nexusDB-tests/Agent-Scope/agent.py](../nexusDB-tests/Agent-Scope/agent.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Funções/classes: `main`.

### [../nexusDB-tests/Agent-Scope/nexusdb_tools.py](../nexusDB-tests/Agent-Scope/nexusdb_tools.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `NexusDBConfig`, `NexusDBAgentAPI`, `nexusdb_database_stats`, `nexusdb_pagerank`, `nexusdb_shortest_path`, `nexusdb_spatial_nearby`, `nexusdb_vector_search`.

### [../nexusDB-tests/Agent-Scope/smoke_test.py](../nexusDB-tests/Agent-Scope/smoke_test.py)

Fonte auxiliar; consulte o programa principal da família.

## Coleção externa: BioGrid

### [../nexusDB-tests/BioGrid/BioGRID-Explorer/app.py](../nexusDB-tests/BioGrid/BioGRID-Explorer/app.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `need`, `resolve`, `ints`, `evidence_row`, `classify`.

### [../nexusDB-tests/BioGrid/BioGRID-Explorer/config.py](../nexusDB-tests/BioGrid/BioGRID-Explorer/config.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `Settings`.

### [../nexusDB-tests/BioGrid/BioGRID-Explorer/graph_ui.py](../nexusDB-tests/BioGrid/BioGRID-Explorer/graph_ui.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `props`, `nid`, `sym`, `triplets`, `fig`.

### [../nexusDB-tests/BioGrid/BioGRID-Explorer/graph_visualization.py](../nexusDB-tests/BioGrid/BioGRID-Explorer/graph_visualization.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `props`, `node_id`, `symbol`, `triplets`, `network_figure`.

### [../nexusDB-tests/BioGrid/BioGRID-Explorer/nexusdb_client.py](../nexusDB-tests/BioGrid/BioGRID-Explorer/nexusdb_client.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `esc`, `NexusDBClient`.

### [../nexusDB-tests/BioGrid/nexusdb_biogrid_importer/import_biogrid_nexusdb.py](../nexusDB-tests/BioGrid/nexusdb_biogrid_importer/import_biogrid_nexusdb.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Opções encontradas: `--input`, `--url`, `--database`, `--user`, `--password`, `--batch-size`, `--all-organisms`, `--admin-database`.

Funções/classes: `clean`, `pick`, `number`, `NexusDB`, `files_for`, `read`, `chunks`, `idmap`, `main`.

### [../nexusDB-tests/BioGrid/run_BioGRID-Explorer.bat](../nexusDB-tests/BioGrid/run_BioGRID-Explorer.bat)

Script operacional; leia efeitos e diretórios alvo antes de executar.

### [../nexusDB-tests/BioGrid/run_import.bat](../nexusDB-tests/BioGrid/run_import.bat)

Script operacional; leia efeitos e diretórios alvo antes de executar.

## Coleção externa: BMSSP-Dijkstra

### [../nexusDB-tests/BMSSP-Dijkstra/bmssp_snap_dimacs.py](../nexusDB-tests/BMSSP-Dijkstra/bmssp_snap_dimacs.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Public dataset loaders and fully validated BMSSP comparison.

Funções/classes: `_maybe_download`, `load_snap_roadnet_CA`, `load_dimacs_florida`, `demo_snap`, `demo_dimacs`.

### [../nexusDB-tests/BMSSP-Dijkstra/grafos.py](../nexusDB-tests/BMSSP-Dijkstra/grafos.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Small BMSSP example. Shared implementation lives in shortest_paths.py.

### [../nexusDB-tests/BMSSP-Dijkstra/grafos2.py](../nexusDB-tests/BMSSP-Dijkstra/grafos2.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

### [../nexusDB-tests/BMSSP-Dijkstra/shortest_paths.py](../nexusDB-tests/BMSSP-Dijkstra/shortest_paths.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Didactic BMSSP with explicit path ordering; no asymptotic speedup claim.

Funções/classes: `add_edge`, `_normalize`, `_State`, `DStruct`, `_base_case`, `_find_pivots`, `_bmssp`, `sssp_break_sorting`, `dijkstra_full`, `compare_with_dijkstra`.

### [../nexusDB-tests/BMSSP-Dijkstra/test_shortest_paths.py](../nexusDB-tests/BMSSP-Dijkstra/test_shortest_paths.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `bellman_ford`, `ShortestPathsTests`.

## Coleção externa: FolhaPagto-Example

### [../nexusDB-tests/FolhaPagto-Example/core.py](../nexusDB-tests/FolhaPagto-Example/core.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Persistência local transacional, folha demonstrativa, auditoria e detecção de anomalias.

Funções/classes: `connect`, `ensure_open`, `close_period`, `load`, `save`, `bootstrap`, `payroll_for`, `entries_for`, `employee_upsert`, `employee_delete`, `set_payment`, `audit`, `anomalies`, `graph_data`, `sync_nexus`, `incremental_sync`; mais 1 símbolos no manifesto.

### [../nexusDB-tests/FolhaPagto-Example/dashboard.py](../nexusDB-tests/FolhaPagto-Example/dashboard.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: NexusDB Empresa: Streamlit. Execute: streamlit run dashboard.py

Funções/classes: `reload`, `fmt`, `filtered`, `total`, `json_dumps`.

### [../nexusDB-tests/FolhaPagto-Example/empresa.py](../nexusDB-tests/FolhaPagto-Example/empresa.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: NexusDB Empresa: demo sintética de RH, folha, contabilidade e grafo.

Opções encontradas: `--url`, `--user`, `--database`, `--employees`, `--months`, `--competence`, `--branch`, `--center`, `--output`, `--limit`.

Funções/classes: `money`, `cents`, `brl`, `NexusClient`, `quote`, `props`, `create`, `relate`, `dataset`, `summarize`, `export`, `upload`, `main`.

### [../nexusDB-tests/FolhaPagto-Example/fiscal.py](../nexusDB-tests/FolhaPagto-Example/fiscal.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Motor fiscal parametrizado: SIMULAÇÃO. Não substitui legislação nem software homologado.

Funções/classes: `amount`, `progressive`, `validate`, `load_rules`, `payroll`, `additional_taxes`.

### [../nexusDB-tests/FolhaPagto-Example/fiscal_ext.py](../nexusDB-tests/FolhaPagto-Example/fiscal_ext.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Motor fiscal adicional, parametrizado por esfera, UF, município, vigência e base.

Funções/classes: `validate_extended`, `simulate_operation`, `simulate_payroll`.

### [../nexusDB-tests/FolhaPagto-Example/nexus_sync.py](../nexusDB-tests/FolhaPagto-Example/nexus_sync.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Outbox segura: serialização, confirmação, invalidação de arestas e leitura remota.

Funções/classes: `setup`, `_node`, `_edge`, `_delete_edge`, `operations`, `enqueue`, `drain`, `investigation_queries`, `remote_graph`.

### [../nexusDB-tests/FolhaPagto-Example/storage.py](../nexusDB-tests/FolhaPagto-Example/storage.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Conexões SQLite por unidade de trabalho, sem conexões compartilhadas entre threads.

Funções/classes: `session`, `initialize`.

### [../nexusDB-tests/FolhaPagto-Example/test_core.py](../nexusDB-tests/FolhaPagto-Example/test_core.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `CoreTests`.

### [../nexusDB-tests/FolhaPagto-Example/test_empresa.py](../nexusDB-tests/FolhaPagto-Example/test_empresa.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `EmpresaTests`.

### [../nexusDB-tests/FolhaPagto-Example/test_evolution.py](../nexusDB-tests/FolhaPagto-Example/test_evolution.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `FakeClient`, `EvolutionTests`.

### [../nexusDB-tests/FolhaPagto-Example/test_v4.py](../nexusDB-tests/FolhaPagto-Example/test_v4.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `FakeClient`, `V4Tests`.

## Coleção externa: geospatial-urban-graph

### [../nexusDB-tests/geospatial-urban-graph/demo.py](../nexusDB-tests/geospatial-urban-graph/demo.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: GeocodeBR + City2Graph + NexusDB urban-service demo.

Opções encontradas: `--geocode-csv`, `--poi-csv`, `--radius-m`, `--url`, `--user`, `--password`, `--database`, `--output`.

Funções/classes: `NexusClient`, `fixture_layers`, `geocode_layers`, `poi_layer`, `build_poi_edges`, `normalize_bairro_name`, `bairro_key`, `bairro_rows`, `bairro_summary`, `poi_node_rows`, `import_poi_graph`, `build_access_edges`, `json_value`, `node_rows`, `edge_endpoints`, `import_graph`; mais 3 símbolos no manifesto.

### [../nexusDB-tests/geospatial-urban-graph/download_niteroi_pois.py](../nexusDB-tests/geospatial-urban-graph/download_niteroi_pois.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Download and normalize official Niterói POIs from the municipal SIGeo ArcGIS services.

Opções encontradas: `--output`, `--ca-bundle`, `--tls-mode`, `--insecure`, `--skip-failed-layers`.

Funções/classes: `first_value`, `build_ssl_context`, `download_geojson`, `normalize_feature`, `main`.

### [../nexusDB-tests/geospatial-urban-graph/interactive_urban_map.py](../nexusDB-tests/geospatial-urban-graph/interactive_urban_map.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Interactive didactic urban graph map for NexusDB.

Funções/classes: `NexusClient`, `_entity_properties`, `_node_frame`, `_near_frame`, `_located_frame`, `load_data`, `build_graph`, `haversine_m`, `format_distance`, `category_palette`, `poi_label`, `make_map`, `nearest_neighbors`, `main`.

### [../nexusDB-tests/geospatial-urban-graph/visualize_urban_graph.py](../nexusDB-tests/geospatial-urban-graph/visualize_urban_graph.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Visualize a NexusDB urban POI graph as static PNG images.

Opções encontradas: `--url`, `--user`, `--password`, `--database`, `--output-dir`.

Funções/classes: `NexusClient`, `fetch_dataframe`, `normalize_columns`, `_entity_properties`, `_node_frame`, `_near_frame`, `_located_frame`, `load_graph_data`, `build_network`, `category_color_map`, `plot_category_map`, `plot_map_and_graph`, `plot_bairro_summary`, `export_top_hubs`, `main`.

## Coleção externa: GraphRag

### [../nexusDB-tests/GraphRag/test_graphRag.py](../nexusDB-tests/GraphRag/test_graphRag.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `cypher`, `check`.

## Coleção externa: GraphRag2

### [../nexusDB-tests/GraphRag2/benchmark_10k.py](../nexusDB-tests/GraphRag2/benchmark_10k.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Benchmark NexusDB Vector/HNSW

Opções encontradas: `--url`, `--user`, `--vectors`, `--dimensions`, `--queries`, `--k`, `--output`.

Funções/classes: `Client`, `normalize`, `generate_vectors`, `dot`, `exact_search`, `recall_at_k`, `percentile`, `upload_vectors`, `nexus_search`, `benchmark`, `main`.

### [../nexusDB-tests/GraphRag2/demo.py](../nexusDB-tests/GraphRag2/demo.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Demo reproduzível do NexusDB:

Opções encontradas: `--url`, `--user`, `--database`, `--order`, `--output`, `--generate-only`.

Funções/classes: `dataset`, `tokens`, `Tfidf`, `Client`, `upload`, `measured`, `dot_product`, `exact_search`, `print_vector_diagnostics`, `evaluate`, `report_html`, `main`.

## Coleção externa: nexusdb-AI

### [../nexusDB-tests/nexusdb-AI/cli.py](../nexusDB-tests/nexusdb-AI/cli.py)

Fonte auxiliar; consulte o programa principal da família.

Opções encontradas: `--question`, `--ollama`, `--model`, `--embedding-model`.

### [../nexusDB-tests/nexusdb-AI/cli_live.py](../nexusDB-tests/nexusdb-AI/cli_live.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Opt-in real API mode. Requires a verified bridge contract file.

Opções encontradas: `--base-url`, `--contract`, `--database`, `--projection`, `--version`, `--question`, `--ollama`, `--algorithm`, `--backend`, `--max-index-nodes`.

Funções/classes: `LimitedGraph`.

### [../nexusDB-tests/nexusdb-AI/nexusdb_ai/__init__.py](../nexusDB-tests/nexusdb-AI/nexusdb_ai/__init__.py)

Inicialização/exportações do pacote; não executar isoladamente.

### [../nexusDB-tests/nexusdb-AI/nexusdb_ai/adapter.py](../nexusDB-tests/nexusdb-AI/nexusdb_ai/adapter.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Explicit adapter contract for connecting to a real NexusDB deployment.

Funções/classes: `NexusDBAdapter`.

### [../nexusDB-tests/nexusdb-AI/nexusdb_ai/core.py](../nexusDB-tests/nexusdb-AI/nexusdb_ai/core.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: NexusDB AI v0.1: local retrieval, safe graph plans, and decision support.

Funções/classes: `tokens`, `cosine`, `Embedding`, `HashEmbedding`, `Ollama`, `Node`, `Edge`, `Graph`, `MemoryGraph`, `QueryPlan`, `execute_plan`, `parse_plan`, `plan_question`, `VectorIndex`, `build_index`, `retrieve`; mais 3 símbolos no manifesto.

### [../nexusDB-tests/nexusdb-AI/nexusdb_ai/http_adapter.py](../nexusDB-tests/nexusdb-AI/nexusdb_ai/http_adapter.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Contract-driven HTTP bridge. No assumptions about actual NexusDB routes.

Funções/classes: `ContractError`, `HttpContract`, `HttpTransport`, `NexusDBHttpAdapter`.

### [../nexusDB-tests/nexusdb-AI/tests/test_core.py](../nexusDB-tests/nexusdb-AI/tests/test_core.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `Tests`.

### [../nexusDB-tests/nexusdb-AI/tests/test_http_adapter.py](../nexusDB-tests/nexusdb-AI/tests/test_http_adapter.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `FakeTransport`, `AdapterTests`.

## Coleção externa: Openfights

### [../nexusDB-tests/Openfights/nexusdb_airroute_resilience_v1/app.py](../nexusDB-tests/Openfights/nexusdb_airroute_resilience_v1/app.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `rows_as_dicts`, `val`, `fnum`, `haversine_km`, `run_query`, `load_nexus`, `build_indexes`, `shortest_path`, `airport_label`, `analyze_airport`, `map_dataframe`, `unwrap_native_payload`, `native_call`, `node_props`, `find_native_node_id`, `format_ms`; mais 14 símbolos no manifesto.

### [../nexusDB-tests/Openfights/nexusdb_airroute_resilience_v1/graph_builder.py](../nexusDB-tests/Openfights/nexusdb_airroute_resilience_v1/graph_builder.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `make_network_html`.

### [../nexusDB-tests/Openfights/nexusdb_airroute_resilience_v1/nexus_client.py](../nexusDB-tests/Openfights/nexusdb_airroute_resilience_v1/nexus_client.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `NexusClient`.

### [../nexusDB-tests/Openfights/nexusdb_airroutes_import/import_openflights_nexusdb.py](../nexusDB-tests/Openfights/nexusdb_airroutes_import/import_openflights_nexusdb.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: OpenFlights .dat -> NexusDB

Opções encontradas: `--folder`, `--url`, `--user`, `--password`, `--database`, `--batch-size`, `--route-limit`, `--use-basic-airports`, `--dry-run`, `--reuse`.

Funções/classes: `clean`, `num`, `compact`, `NexusClient`, `read_rows`, `chunks`, `load_sources`, `prepare`, `main`.

### [../nexusDB-tests/Openfights/run_import.bat](../nexusDB-tests/Openfights/run_import.bat)

Script operacional; leia efeitos e diretórios alvo antes de executar.

### [../nexusDB-tests/Openfights/run_testa_rotas.bat](../nexusDB-tests/Openfights/run_testa_rotas.bat)

Script operacional; leia efeitos e diretórios alvo antes de executar.

## Coleção externa: phorenesis

### [../nexusDB-tests/phorenesis/testar_phronesis.py](../nexusDB-tests/phorenesis/testar_phronesis.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Laboratório didático NexusDB: chamadas reais, sem simular respostas.

Opções encontradas: `--url`, `--usuario`, `--banco`, `--escrita`, `--saida`.

Funções/classes: `NexusError`, `Client`, `first`, `scenario`, `main`.

## Coleção externa: SuplyChain-Ford-Kaggle

### [../nexusDB-tests/SuplyChain-Ford-Kaggle/import_supply_chain_nexusdb.py](../nexusDB-tests/SuplyChain-Ford-Kaggle/import_supply_chain_nexusdb.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Importador Supply Chain Kaggle -> NexusDB.

Opções encontradas: `--csv`, `--url`, `--user`, `--password`, `--database`, `--limit`, `--batch-size`, `--timeout`.

Funções/classes: `NexusClient`, `BatchWriter`, `s`, `number`, `compact`, `main`.

### [../nexusDB-tests/SuplyChain-Ford-Kaggle/importa.bat](../nexusDB-tests/SuplyChain-Ford-Kaggle/importa.bat)

Script operacional; leia efeitos e diretórios alvo antes de executar.

### [../nexusDB-tests/SuplyChain-Ford-Kaggle/run_suply.bat](../nexusDB-tests/SuplyChain-Ford-Kaggle/run_suply.bat)

Script operacional; leia efeitos e diretórios alvo antes de executar.

### [../nexusDB-tests/SuplyChain-Ford-Kaggle/supply_chain_demo/app.py](../nexusDB-tests/SuplyChain-Ford-Kaggle/supply_chain_demo/app.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `add_node`, `add_edge`, `load_csv`, `rows_as_dicts`, `val`, `load_nexus`, `display`.

### [../nexusDB-tests/SuplyChain-Ford-Kaggle/supply_chain_demo/graph_builder.py](../nexusDB-tests/SuplyChain-Ford-Kaggle/supply_chain_demo/graph_builder.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `make_html`.

### [../nexusDB-tests/SuplyChain-Ford-Kaggle/supply_chain_demo/impact_analysis.py](../nexusDB-tests/SuplyChain-Ford-Kaggle/supply_chain_demo/impact_analysis.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `build_indexes`, `analyze_removal`.

### [../nexusDB-tests/SuplyChain-Ford-Kaggle/supply_chain_demo/nexus_client.py](../nexusDB-tests/SuplyChain-Ford-Kaggle/supply_chain_demo/nexus_client.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `NexusClient`.

### [../nexusDB-tests/SuplyChain-Ford-Kaggle/supply_chain_demo/risk_analysis.py](../nexusDB-tests/SuplyChain-Ford-Kaggle/supply_chain_demo/risk_analysis.py)

Fonte auxiliar; consulte o programa principal da família.

Funções/classes: `_num`, `_indexes`, `_sources`, `_targets`, `analyze_supply_risk`.

## Coleção externa: nexusdb_python_tests

### [../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_api_real/manual_suite_original.py](../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_api_real/manual_suite_original.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Suíte do Manual Prático NexusDB usando diretamente a biblioteca Rust nativa.

Opções encontradas: `--library`, `--db`, `--report`, `--reset`, `--only-tests`.

Funções/classes: `eq`, `col`, `one`, `Suite`, `main`.

### [../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_api_real/nexusdb_rest.py](../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_api_real/nexusdb_rest.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: Cliente NexusDB conforme demo(1).py: POST /db/data/cypher e cabeçalhos X-*.

Funções/classes: `NexusDBRestError`, `RestConfig`, `NexusDBRest`.

### [../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_api_real/run_rest_suite.py](../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_api_real/run_rest_suite.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Executa testes Cypher do manual em bancos exclusivos, sem apagar dados por padrão.

Opções encontradas: `--url`, `--user`, `--password`, `--db`, `--prefix`, `--report`, `--only-tests`, `--cleanup`.

Funções/classes: `RestSuite`, `main`.

### [../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_api_real/test_rest_adapter.py](../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_api_real/test_rest_adapter.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `Handler`, `Tests`.

### [../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_tests/manual_suite_original.py](../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_tests/manual_suite_original.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Suíte do Manual Prático NexusDB usando diretamente a biblioteca Rust nativa.

Opções encontradas: `--library`, `--db`, `--report`, `--reset`, `--only-tests`.

Funções/classes: `eq`, `col`, `one`, `Suite`, `main`.

### [../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_tests/nexusdb_rest.py](../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_tests/nexusdb_rest.py)

Fonte auxiliar; consulte o programa principal da família.

Descrição na fonte: NexusDB REST adapter. Endpoint templates must match the deployed NexusDB API.

Funções/classes: `NexusDBRestError`, `RestConfig`, `NexusDBRest`.

### [../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_tests/run_rest_suite.py](../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_tests/run_rest_suite.py)

Programa com ponto de entrada Python; veja requisitos e efeitos antes de executar.

Descrição na fonte: Executa todos os testes do manual contra NexusDB REST, isolando cada caso em um banco temporário.

Opções encontradas: `--url`, `--db`, `--prefix`, `--report`, `--reset`, `--only-tests`.

Funções/classes: `RestSuite`, `main`.

### [../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_tests/test_rest_adapter.py](../nexusDB-tests/nexusdb_python_tests/nexusdb_rest_tests/test_rest_adapter.py)

Teste de aplicação; não confundir com um cliente de uso cotidiano.

Funções/classes: `Handler`, `RestAdapterTest`.

## Protótipos de referência: extensão de grafo

### [../nexusDB-tests/graph-extension-reference/nexusdb_graph_extension/src/cypher.rs](../nexusDB-tests/graph-extension-reference/nexusdb_graph_extension/src/cypher.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `invalid`, `split_top`, `parse_value`, `parse_properties`, `pattern`, `clauses`, `matches_where`, `remove_nodes`, `execute`, `project`, `cypher_crud`, `deletion_remaps_edges`, `rejects_unsupported`.

### [../nexusDB-tests/graph-extension-reference/nexusdb_graph_extension/src/lib.rs](../nexusDB-tests/graph-extension-reference/nexusdb_graph_extension/src/lib.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `from_edges`, `validate`, `vertices`, `edges`, `neighbors`, `transpose`, `default`, `effective_backend`, `spmv_plus_times`, `spmv_boolean`, `bfs`, `dijkstra`, `pagerank`, `index_key`, `add_vertex`, `add_edge`; mais 11 símbolos no manifesto.

### [../nexusDB-tests/graph-extension-reference/nexusdb_graph_extension/tests/regression.rs](../nexusDB-tests/graph-extension-reference/nexusdb_graph_extension/tests/regression.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `edges`, `graph`, `seq`, `regression_01_csr_build_validate_transpose`, `regression_02_generic_spmv_and_boolean_semiring`, `regression_03_bfs_unreachable_and_bad_source`, `regression_04_dijkstra_weighted_and_negative_guard`, `regression_05_pagerank_dangling_mass_and_empty_graph`, `regression_06_property_graph_json_and_csr_projection`, `regression_07_equality_index_update_and_rebuild`, `regression_08_query_filter_nodes_and_relationships`, `regression_09_rayon_matches_sequential`, `regression_10_auto_threshold_and_cuda_fallback`.

## Protótipos de referência: espacial

### [../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/examples/hospitals.rs](../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/examples/hospitals.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `main`.

### [../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/examples/spatial_pipeline.rs](../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/examples/spatial_pipeline.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `main`.

### [../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/advanced.rs](../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/advanced.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `new`, `to_wgs84`, `new`, `length_m`, `envelope`, `distance_2`, `default`, `new`, `len`, `get`, `upsert`, `remove`, `bbox`, `polygon`, `radius`, `index_and_antimeridian`; mais 1 símbolos no manifesto.

### [../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/cypher.rs](../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/cypher.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `from`, `evaluate`, `dispatch`.

### [../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/geoparquet.rs](../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/geoparquet.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `from`, `from`, `wkb_point`, `import_wkb_points`, `parse_point`.

### [../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/gis.rs](../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/gis.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `from`, `from`, `point_from_coords`, `import_points`, `export_points`, `export_route`, `roundtrip`.

### [../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/graph.rs](../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/graph.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `validate`, `filtered`, `within_bbox`, `geographic_dijkstra`, `cmp`, `partial_cmp`, `filter_and_path`.

### [../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/lib.rs](../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/lib.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `fmt`, `new`, `haversine_m`, `new`, `contains`, `intersects`, `new`, `contains`, `bounds`, `new`, `upsert`, `remove`, `get`, `len`, `is_empty`, `within_bbox`; mais 14 símbolos no manifesto.

### [../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/temporal.rs](../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/nexusdb-spatial/src/temporal.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `snapshot`, `window_edges`, `snapshots`.

### [../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/src/lib.rs](../nexusDB-tests/spatial-reference-v1/nexusdb-spatial-integration-v1/src/lib.rs)

Protótipo de referência, separado do núcleo atual; não instalar como dependência do livro.

Funções/classes: `point`, `active_at`, `snapshot_spatial`, `version`, `len`, `record`, `apply_committed`, `bbox`, `radius`, `visible`, `spatial_subgraph`, `evaluate_spatial_function`, `snapshot_spatial`, `rebuild_and_temporal_filter`, `rejects_gap_without_mutation`, `rejects_invalid_batch_atomically`.

