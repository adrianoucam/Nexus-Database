# Testar acesso REST por chaves temporárias

O [gateway Rust/Axum](../crates/nexusdb-rest-gateway/README.md) publica operações de leitura delimitadas por database, label/tipo de relacionamento, propriedades e parâmetros. Aceita X-API-Key ou Bearer; chaves têm duração e podem ser desativadas individualmente, por endpoint, database ou globalmente.

```powershell
cd E:\nexusdb
cargo build --features phronesis,datalog,embedded,spatial-geoparquet --bin nexusdb
cargo build --manifest-path crates/nexusdb-rest-gateway/Cargo.toml
py examples/rest_gateway_validation.py --output E:\nexusDB-tests\rest-gateway-output
```

Requisitos: Rust/Cargo, Python padrão e executáveis compilados. A demonstração cria servidores em portas livres, seis leitos e cinco relacionamentos fictícios, databases EXAMPLE_REST_GATEWAY/EXAMPLE_REST_PHRONESIS/EXAMPLE_REST_DENIED e uma conta READ isolada. Executa os contratos de consulta, autenticação, RBAC, prazo, revogação/reinício, PageRank, Phronesis e o adaptador AI do anexo. Fecha apenas seus processos e mantém report.json e logs sem chaves/senhas. Não toca no serviço instalado.

Para executar seus próprios clientes, siga as instruções administrativas de [criação de chaves, consulta e bloqueio](../crates/nexusdb-rest-gateway/README.md). Uma chave emitida para a porta 8787 não autentica diretamente na porta nativa 7474. Use contas READ dedicadas e apenas os campos que deseja publicar.

O teste Rust adicional bloqueia acesso enquanto o upstream ainda está calculando e verifica que o gateway descarta os dados da resposta. Expiração usa o relógio UTC real; o teste Python aguarda o deadline retornado pelo servidor, sem assumir uma latência exata.

Limitações: somente POST de dados e JSON; sem streaming/CSV/JWT; TLS remoto via proxy; operações de escrita/decisão não são publicadas. Limite de linhas é de topo e não substitui o orçamento de cálculo do núcleo. Sem alegação de performance ou CUDA real. Licença igual à [raiz](../LICENSE).
