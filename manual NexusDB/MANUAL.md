# Manual básico do NexusDB — primeiros passos com Python e PHP

**Edição 1.0 | Base técnica: NexusDB Graph Extension v0.5 (experimental) | Outubro de 2026**

> **Atenção:** este manual documenta a extensão Rust fornecida neste projeto, e **não** uma distribuição completa e instalada do NexusDB. A extensão possui um grafo em memória e uma ponte JSON criada para testes de conformidade. Não há, no pacote examinado, um servidor HTTP, SDK oficial Python/PHP, autenticação, persistência em disco ou transações ACID. Os exemplos de Python e PHP usam a ponte existente, sem inventar APIs.

## 1. O que é um banco de grafos?

Um banco de grafos representa entidades como **vértices (nós)** e ligações como **arestas (relacionamentos)**. Por exemplo: um cliente é um nó; uma compra pode ser um relacionamento entre cliente e produto. Cada entidade pode possuir propriedades, como nome e cidade.

O NexusDB Graph Extension é uma biblioteca Rust experimental que oferece estruturas CSR, algoritmos de grafos, propriedades JSON, índices e um subconjunto da linguagem Cypher.

**Quando utilizar grafos?** Quando o problema exige percorrer ligações, identificar conexões, descobrir rotas ou analisar redes. Para uma lista simples de clientes sem relacionamentos, um banco relacional pode ser mais conveniente.

## 2. Conceitos fundamentais

| Termo | Significado | Exemplo |
|---|---|---|
| Nó | Entidade | Cliente Ana |
| Rótulo | Categoria de nó | `:Cliente` |
| Propriedade | Dado de um nó | `nome: 'Ana'` |
| Relacionamento | Ligação entre nós | `:COMPROU` |
| Cypher | Linguagem para descrever padrões e consultas | `MATCH (n:Cliente) RETURN n.nome` |
| CSR | Representação compacta de adjacência para algoritmos | Usada por BFS e PageRank |
| TCK | Conjunto de testes de conformidade da linguagem | Cenários Gherkin `.feature` |

**Limitação atual:** a biblioteca Rust armazena arestas e permite consultá-las pela API Rust, mas o interpretador Cypher v0.5 **não executa** padrões de relacionamento como `MATCH (a)-[:COMPROU]->(b)`.

## 3. Preparação do ambiente

Instale Rust e Cargo a partir de https://rustup.rs/ . Instale Python 3 ou PHP CLI conforme a linguagem escolhida. Extraia o pacote `nexusdb_graph_extension_v0.5_tck.zip` e abra um terminal na pasta `nexusdb_graph_extension` (onde está o `Cargo.toml`).

No Windows (PowerShell):

```powershell
cargo --version
cargo test --all-targets
cargo build --release --bin tck_bridge
python .\exemplos\python_basico.py .\target\release\tck_bridge.exe
php .\exemplos\php_basico.php .\target\release\tck_bridge.exe
```

No Linux/macOS:

```bash
cargo test --all-targets
cargo build --release --bin tck_bridge
python3 exemplos/python_basico.py ./target/release/tck_bridge
php exemplos/php_basico.php ./target/release/tck_bridge
```

**Observação:** copie a pasta `exemplos` deste manual para dentro do projeto Rust antes de executar os dois últimos comandos. Os comandos de compilação não foram validados neste ambiente de elaboração.

## 4. Como a comunicação funciona

Os programas Python/PHP iniciam o executável Rust `tck_bridge`, enviam um JSON pela entrada padrão (stdin) e leem um JSON pela saída padrão (stdout).

Exemplo de pedido:

```json
{
  "setup": ["CREATE (n:Cliente {nome: 'Ana'})"],
  "query": "MATCH (n:Cliente) RETURN n.nome"
}
```

A resposta tem campos `ok`, `rows`, `before`, `after`, `error` e `stage`. `rows` é uma lista de registros (mapas JSON). Em caso de erro, verifique `ok` e `error`.

**Importante:** a ponte cria um grafo vazio para **cada requisição**, aplica `setup` e executa `query`. Portanto, **não mantém dados entre requisições**. Os exemplos reproduzem os dados iniciais em cada consulta. Isso é adequado para aprendizagem e testes, mas não para produção.

## 5. Criando seus primeiros dados

```cypher
CREATE (n:Cliente {nome: 'Ana', cidade: 'Niteroi'})
```

Para criar outro cliente:

```cypher
CREATE (n:Cliente {nome: 'Bruno', cidade: 'Rio'})
```

Cada instrução `CREATE` cria um nó em memória. A sintaxe de propriedades utiliza pares `chave: valor`.

## 6. Consultando os clientes

Todos os clientes:

```cypher
MATCH (n:Cliente)
RETURN n.nome, n.cidade
```

Somente clientes de determinada cidade:

```cypher
MATCH (n:Cliente)
WHERE n.cidade = 'Rio'
RETURN n.nome
```

Quantidade de clientes:

```cypher
MATCH (n:Cliente)
RETURN count(n)
```

Limitar resultados:

```cypher
MATCH (n:Cliente)
RETURN n.nome
LIMIT 5
```

**Dica:** a v0.5 suporta comparações de igualdade simples em `WHERE`, não filtros gerais com `AND`, `OR`, intervalos e funções arbitrárias.

## 7. Atualizando e excluindo dados

Alterar uma propriedade:

```cypher
MATCH (n:Cliente)
WHERE n.nome = 'Ana'
SET n.cidade = 'Petropolis'
```

Remover uma propriedade:

```cypher
MATCH (n:Cliente)
WHERE n.nome = 'Ana'
REMOVE n.cidade
```

Excluir um nó sem relacionamentos:

```cypher
MATCH (n:Cliente)
WHERE n.nome = 'Ana'
DELETE n
```

Excluir um nó com seus relacionamentos:

```cypher
MATCH (n:Cliente)
WHERE n.nome = 'Ana'
DETACH DELETE n
```

**Cuidado:** esta versão utiliza identificadores posicionais internos. Exclusões podem alterar os IDs dos nós remanescentes; não use `id(n)` como identificador de negócio permanente.

## 8. Exemplo completo em Python

O arquivo `exemplos/python_basico.py` acompanha este manual. Ele utiliza `subprocess.run` e `json`, sem bibliotecas externas. A função `consultar(setup, query)` valida o campo `ok` antes de devolver as linhas.

```python
historico = [
    "CREATE (n:Cliente {nome: 'Ana', cidade: 'Niteroi'})",
    "CREATE (n:Cliente {nome: 'Bruno', cidade: 'Rio'})",
]
print(consultar(historico, 'MATCH (n:Cliente) RETURN n.nome, n.cidade'))
```

Execute a partir da pasta do projeto Rust. O exemplo completo inclui consultas por cidade e contagem.

## 9. Exemplo completo em PHP

O arquivo `exemplos/php_basico.php` utiliza `proc_open()` para comunicar-se com a ponte Rust. Não depende de extensões de banco de dados nem de frameworks PHP.

```php
$historico = [
    "CREATE (n:Cliente {nome: 'Ana', cidade: 'Niteroi'})",
    "CREATE (n:Cliente {nome: 'Bruno', cidade: 'Rio'})"
];
$linhas = consultar($bin, $historico, 'MATCH (n:Cliente) RETURN n.nome');
echo json_encode($linhas, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
```

Para projetos web, **não exponha essa ponte diretamente a usuários externos**. A ponte não implementa autenticação, autorização, isolamento de clientes, limitação de recursos nem persistência.

## 10. Funcionalidades disponíveis e pendentes

| Recurso | Estado na extensão v0.5 | Uso em Python/PHP pela ponte |
|---|---|---|
| Criar nós e propriedades | Subconjunto funcional | Sim |
| Buscar nós por rótulo | Subconjunto funcional | Sim |
| `WHERE` com igualdade | Subconjunto funcional | Sim |
| `RETURN`, `count(n)`, `LIMIT` | Subconjunto funcional | Sim |
| `SET`, `REMOVE`, `DELETE`, `DETACH DELETE` | Subconjunto funcional | Sim, com ressalvas |
| Criar e consultar relacionamentos | API Rust disponível | Não via Cypher atual |
| BFS, Dijkstra, PageRank, SpMV | API Rust disponível | Não via ponte atual |
| Rayon e seleção AUTO | API Rust disponível | Não configuráveis via ponte |
| Consultas `MERGE`, `OPTIONAL MATCH`, `UNWIND`, `UNION` | Não implementadas no executor | Não |
| Servidor, persistência, transações ACID | Não demonstrados neste pacote | Não |
| Testes de conformidade TCK M23 | Executor progressivo | Ferramenta de desenvolvimento |

## 11. Dez ideias de aplicações simples

1. Cadastro de clientes e busca por cidade.
2. Catálogo de produtos por categoria.
3. Cadastro de médicos e pacientes (somente dados fictícios na versão atual).
4. Inventário de equipamentos.
5. Catálogo de livros.
6. Cadastro de fornecedores.
7. Cadastro de alunos por turma.
8. Controle simples de ativos.
9. Lista de projetos e responsáveis.
10. Protótipo de análise de redes — exige ampliar a ponte para relacionamentos e algoritmos.

Os exemplos 1 a 9 podem começar como cadastros simples de nós. **Não** são sistemas completos de produção, pois falta persistência e segurança de acesso.

## 12. Erros comuns

**“Arquivo tck_bridge não encontrado”** — execute `cargo build --release --bin tck_bridge` e confira o caminho do executável.

**“unsupported or malformed Cypher query”** — utilize apenas o subconjunto descrito no capítulo 10; por exemplo, padrões de arestas não são aceitos pelo executor atual.

**“Não encontro dados criados na consulta anterior”** — cada chamada da ponte inicia um grafo novo. Inclua a criação dos dados em `setup` ou desenvolva uma API persistente.

**“Os IDs mudaram após excluir nós”** — IDs são posicionais nesta implementação. Armazene uma propriedade de identificação de negócio e evite assumir estabilidade de `id(n)`.

**“O PHP não consegue executar o programa”** — verifique permissões, configuração de `proc_open` e caminho do executável.

## 13. Boas práticas

- Use rótulos no singular, como `:Cliente`, `:Produto`.
- Use nomes de propriedades claros, como `dataCadastro`.
- Escreva palavras-chave Cypher em maiúsculas e strings entre aspas simples.
- Use valores parametrizados quando existir uma API própria para isso; **a ponte atual não oferece parâmetros**, portanto não concatene dados não confiáveis diretamente em consultas.
- Não armazene dados sensíveis de pacientes, clientes ou colaboradores na versão experimental.
- Não confunda “consulta reconhecida pelo lexer” com “consulta executável”.

## 14. Como acompanhar a compatibilidade

A v0.5 inclui `compatibility/tck_results.json` e `compatibility/tck_results.csv`, além de `scripts/tck_runner.py`. Para gerar um relatório novo, compile a ponte e execute:

```bash
python3 scripts/tck_runner.py --strict
```

Os cenários recebem estados `passed`, `failed`, `ignored` e `unsupported`. **Cenários não executados não podem ser contabilizados como aprovados.** A existência dos arquivos de relatório não certifica conformidade integral com openCypher.

## 15. Próximos passos para criar aplicações reais

Para evoluir de protótipo para sistema: criar persistência e transações, estabelecer IDs estáveis, disponibilizar uma API de serviço com autenticação e autorização, adicionar parâmetros de consulta, expor relacionamentos e algoritmos para Python/PHP, implantar limites de CPU/RAM e ampliar os testes TCK.

## Referências e base documental

- Código-fonte NexusDB Graph Extension v0.5, especialmente `src/cypher.rs`, `src/lib.rs` e `src/bin/tck_bridge.rs`.
- openCypher 9, documento de referência da linguagem fornecido no projeto.
- Cypher Style Guide, documento fornecido no projeto.
- Gramática `Cypher.g4` e TCK M23, arquivos fornecidos no projeto.

**Nota de escopo:** os exemplos são demonstrativos, reproduzíveis com a ponte experimental e não representam conectores oficiais NexusDB Python ou PHP.
