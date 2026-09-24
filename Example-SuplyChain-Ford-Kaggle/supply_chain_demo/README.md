# NexusDB Supply Chain Demo v3

## Correção de autenticação

A V3 impede que um clique com senha incorreta dispare as cinco consultas de carga.

1. O botão **Conectar / carregar grafo** faz um pre-flight autenticado (`CALL DB.STATS()`).
2. Se esse primeiro request falhar, a carga é abortada imediatamente.
3. Se funcionar, o grafo é carregado.
4. O resultado fica em `st.session_state`. Trocar fornecedor, produto, checkbox ou filtros não acessa novamente o NexusDB.
5. **Desconectar / limpar sessão** remove o grafo em memória.

> Observação: o protocolo HTTP atual do NexusDB autentica cada requisição por `X-User`/`X-Pass`; portanto não existe sessão/token de login reutilizável no servidor. A V3 garante uma única tentativa em caso de credencial incorreta e evita reconexões causadas pelos reruns do Streamlit. Após um pre-flight correto, as consultas de carga ainda são requisições HTTP autenticadas normais.

## Executar

```powershell
python -m streamlit run supply_chain_demo\app.py
```


## V4

Correção do parser para o formato nativo atual do NexusDB. O endpoint
`/db/data/cypher` retorna `resultados` como uma lista de objetos JSON cujas
chaves são as projeções do `RETURN`, por exemplo `s.supplier_id`,
`s.name`, `p.product_id`, `p.car_maker` e `p.car_model`.

A proteção contra múltiplas tentativas de autenticação da V3 foi mantida.


## V5 — Supply Chain Risk Analyzer

A V5 acrescenta quatro áreas analíticas:

- **Impacto**: produtos bloqueados/em risco, pedidos, clientes, quantidade e receita exposta.
- **Risco**: score 0–100 com decomposição transparente por dependência, pedidos, receita, clientes e centralidade.
- **Alternativas**: fornecedores alternativos observados para o mesmo produto.
- **Caminhos afetados**: Supplier/Product → Product/Order → Customer.

Também corrige o tooltip do PyVis para não exibir tags HTML literalmente.

### Limitação metodológica

O dataset demonstra relações observadas de fornecimento e pedidos. Um fornecedor
alternativo no grafo não implica automaticamente capacidade, estoque, homologação,
lead time ou substituição industrial. Para um modelo de continuidade de produção
mais rigoroso, acrescente nós `Component`, relações `REQUIRES`, estoques, lead times,
capacidade e regras de substituição.
