# NexusDB na prática
## Um guia introdutório para bancos de grafos com exemplos em Cypher, Python e PHP

**Edição didática 1.0 — outubro de 2026**  
**Base técnica verificada:** código-fonte `nexusdb_graph_extension_v0.5_tck` fornecido no projeto.

> **Sobre este livro.** Esta obra é um texto original, organizado segundo uma progressão didática semelhante à do livro de Eduardo Gonçalves, *SQL — Uma abordagem para banco de dados Oracle*: conceitos, ambiente, comandos, consultas, manipulação, integridade e assuntos avançados. Os textos, os dados e os exercícios foram redigidos especificamente para o NexusDB. Não são reproduções de capítulos do livro de referência.
>
> **Atenção à versão.** A extensão v0.5 é um **motor experimental de grafos em memória**, escrito em Rust. Seu executor aceita um **subconjunto** de Cypher. A ponte `tck_bridge` é uma ferramenta de teste por JSON, não um servidor, driver ou banco persistente. O que está marcado **[IMPLEMENTADO v0.5]** pode ser executado pelo executor indicado; **[CONCEITUAL / FUTURO]** mostra a forma desejada em Cypher ou o equivalente de um SGBD tradicional, mas **não é executável nesta versão**. Nenhuma consulta deste livro deve ser interpretada como promessa de compatibilidade integral com openCypher.

---

# Sumário

1. [Por que bancos de dados?](#capítulo-1--por-que-bancos-de-dados)
2. [Bancos relacionais e bancos de grafos](#capítulo-2--bancos-relacionais-e-bancos-de-grafos)
3. [Conhecendo o NexusDB](#capítulo-3--conhecendo-o-nexusdb)
4. [Preparando o ambiente](#capítulo-4--preparando-o-ambiente)
5. [Nosso banco de exemplo: uma empresa](#capítulo-5--nosso-banco-de-exemplo-uma-empresa)
6. [Criando nós: CREATE](#capítulo-6--criando-nós-create)
7. [Consultando dados: MATCH e RETURN](#capítulo-7--consultando-dados-match-e-return)
8. [Filtrando e limitando resultados](#capítulo-8--filtrando-e-limitando-resultados)
9. [Alterando e excluindo registros](#capítulo-9--alterando-e-excluindo-registros)
10. [Tipos de dados e expressões](#capítulo-10--tipos-de-dados-e-expressões)
11. [Relacionamentos e JOINs](#capítulo-11--relacionamentos-e-joins)
12. [Funções, agrupamentos e ordenação](#capítulo-12--funções-agrupamentos-e-ordenação)
13. [Integridade, índices, usuários e transações](#capítulo-13--integridade-índices-usuários-e-transações)
14. [Usando NexusDB com Python](#capítulo-14--usando-nexusdb-com-python)
15. [Usando NexusDB com PHP](#capítulo-15--usando-nexusdb-com-php)
16. [Algoritmos de grafos e aplicações](#capítulo-16--algoritmos-de-grafos-e-aplicações)
17. [Projeto guiado e exercícios](#capítulo-17--projeto-guiado-e-exercícios)
18. [Referência rápida e solução de problemas](#capítulo-18--referência-rápida-e-solução-de-problemas)
19. [Referências e notas editoriais](#referências-e-notas-editoriais)

---

# Capítulo 1 — Por que bancos de dados?

Imagine uma empresa que mantém uma planilha de funcionários e outra de departamentos. Na primeira, o departamento de Ana aparece como **Tecnologia**; na segunda, alguém digitou **Tecnlogia**. Embora pareçam informações simples, agora existem dois nomes para a mesma unidade. Como descobrir quem trabalha em cada departamento sem produzir erros?

Bancos de dados ajudam a organizar informações, reduzir redundâncias, controlar alterações e realizar consultas. Um banco relacional normalmente representa a empresa em tabelas. Um banco de grafos acrescenta uma representação particularmente conveniente quando as **ligações** entre entidades são importantes.

Ao final deste manual, você saberá cadastrar funcionários, recuperar propriedades, filtrar resultados, modificar dados e compreender como representar departamentos, chefias e projetos por relacionamentos.

**Exercício 1.1.** Identifique três situações em que saber *quem está ligado a quem* é mais importante que listar registros: por exemplo, redes de fornecedores, encaminhamento de pacientes e dependências entre componentes de software.

# Capítulo 2 — Bancos relacionais e bancos de grafos

## 2.1. Tabelas, linhas e colunas

Em SQL, poderíamos organizar os dados assim:

**DEPARTAMENTO**

| id | nome | cidade |
|---:|---|---|
| 10 | Tecnologia | Niterói |
| 20 | Financeiro | Rio de Janeiro |
| 30 | Recursos Humanos | Niterói |

**FUNCIONARIO**

| matricula | nome | cargo | salario | departamento_id |
|---:|---|---|---:|---:|
| 101 | Ana Lima | Analista | 6500 | 10 |
| 102 | Bruno Costa | Desenvolvedor | 7800 | 10 |
| 103 | Carla Mendes | Contadora | 7200 | 20 |
| 104 | Diego Rocha | Assistente | 3900 | 30 |
| 105 | Elisa Nunes | Analista | 6100 | 10 |

O campo `departamento_id` funciona como uma **chave estrangeira** em um modelo relacional. No grafo, podemos representar a ligação diretamente.

## 2.2. Nós, rótulos, propriedades e relacionamentos

```text
(Ana Lima:Funcionario) ──[:TRABALHA_EM]──> (Tecnologia:Departamento)
(Bruno Costa:Funcionario) ──[:TRABALHA_EM]──> (Tecnologia:Departamento)
(Carla Mendes:Funcionario) ──[:TRABALHA_EM]──> (Financeiro:Departamento)
```

- **Nó:** uma entidade, como Ana ou Tecnologia.
- **Rótulo:** uma categoria, como `:Funcionario`.
- **Propriedade:** um atributo, como `salario: 6500`.
- **Relacionamento:** uma conexão, como `:TRABALHA_EM`.
- **Direção:** informa de onde a conexão parte e aonde chega.

## 2.3. Correspondência SQL → Cypher

| Banco relacional | Grafo de propriedades | Exemplo |
|---|---|---|
| Tabela | Rótulo de nó | `:Funcionario` |
| Linha | Nó | `(f:Funcionario)` |
| Coluna | Propriedade | `f.nome` |
| `INSERT` | `CREATE` | `CREATE (f:Funcionario {...})` |
| `SELECT` | `MATCH ... RETURN` | `MATCH (f:Funcionario) RETURN f.nome` |
| `UPDATE` | `MATCH ... SET` | `MATCH ... SET f.salario = 7000` |
| `DELETE` | `MATCH ... DELETE` | `MATCH ... DELETE f` |
| `JOIN` | Travessia de relacionamentos | **[CONCEITUAL / FUTURO]** |

**Importante:** a correspondência é didática, não uma tradução automática de qualquer consulta SQL.

# Capítulo 3 — Conhecendo o NexusDB

## 3.1. O que a extensão estudada contém?

O projeto em Rust fornece um grafo de propriedades, representação CSR para processamento de grafos, funções de análise e um executor Cypher restrito. A versão analisada também possui um executor de cenários TCK para medir parte da compatibilidade com a linguagem.

**[IMPLEMENTADO v0.5 — via Cypher]**

| Comando | Situação |
|---|---|
| `CREATE (n:Rotulo {...})` | Cria um nó |
| `MATCH (n:Rotulo)` | Seleciona nós |
| `WHERE n.campo = valor` | Igualdade simples |
| `RETURN n.campo, n.outroCampo` | Retorna propriedades |
| `RETURN n` e `RETURN id(n)` | Retorna nó ou ID interno |
| `RETURN count(n)` | Conta nós encontrados |
| `LIMIT número` | Limita resultados de `RETURN` |
| `SET n.campo = valor` | Altera propriedade |
| `REMOVE n.campo` | Remove propriedade |
| `DELETE n` | Exclui nós sem conexões |
| `DETACH DELETE n` | Exclui nós e suas conexões |

**[CONCEITUAL / FUTURO — não disponível no executor v0.5]**

`ORDER BY`, `DISTINCT`, `SKIP`, `MERGE`, `OPTIONAL MATCH`, `UNWIND`, `WITH`, `UNION`, `CREATE` de arestas, `MATCH` de padrões com arestas, `SUM`, `AVG`, `MIN`, `MAX`, filtros compostos, transações SQL/ACID e controle de privilégios por Cypher.

## 3.2. O que acontece quando executamos uma consulta?

```text
Python ou PHP
     |
     | JSON: {"setup": [...], "query": "..."}
     v
 tck_bridge (processo Rust)
     |
     +--> cria grafo vazio
     +--> executa cada instrução de setup
     +--> executa UMA instrução query
     +--> devolve JSON com linhas e erros
     v
Python ou PHP interpreta a resposta
```

**Cada requisição começa com um grafo vazio.** Dados criados em uma chamada não estarão presentes na próxima, a menos que sejam reenviados em `setup`. Isso não equivale a um banco persistente.

# Capítulo 4 — Preparando o ambiente

## 4.1. Requisitos

Você precisará de Rust/Cargo, do código-fonte da extensão v0.5 e, conforme sua escolha, Python 3 ou PHP CLI. O compilador Rust pode ser instalado por meio de <https://rustup.rs/>. Não é necessário instalar bibliotecas Python externas.

## 4.2. Compilação

Abra o terminal na pasta que contém `Cargo.toml`.

**Windows / PowerShell**

```powershell
cargo --version
cargo test --all-targets
cargo build --release --bin tck_bridge
```

O executável normalmente ficará em `target\release\tck_bridge.exe`.

**Linux / macOS**

```bash
cargo --version
cargo test --all-targets
cargo build --release --bin tck_bridge
```

O executável normalmente ficará em `target/release/tck_bridge`.

> Os comandos foram conferidos contra a estrutura do código-fonte, mas **não foram executados nem validados neste ambiente de elaboração**. O resultado depende do seu compilador e do projeto local.

## 4.3. Sua primeira requisição

O protocolo da ponte aceita `setup` (lista de instruções) e `query` (uma instrução). Exemplo de entrada:

```json
{
  "setup": ["CREATE (f:Funcionario {matricula: 101, nome: 'Ana Lima'})"],
  "query": "MATCH (f:Funcionario) RETURN f.nome"
}
```

A resposta contém `ok`, `rows`, `before`, `after`, `error` e `stage`. O campo `rows` contém os resultados, e `ok` indica sucesso. **Não use esta ponte diretamente como serviço público.**

# Capítulo 5 — Nosso banco de exemplo: uma empresa

Acompanharemos a empresa fictícia **Horizonte Digital**. Ela possui três departamentos e cinco funcionários. Os valores são inteiramente simulados.

## 5.1. Script de preparação

Salve o conjunto abaixo como referência. Na ponte JSON, cada linha será um elemento do vetor `setup`.

```cypher
CREATE (d:Departamento {codigo: 10, nome: 'Tecnologia', cidade: 'Niteroi'})
CREATE (d:Departamento {codigo: 20, nome: 'Financeiro', cidade: 'Rio de Janeiro'})
CREATE (d:Departamento {codigo: 30, nome: 'Recursos Humanos', cidade: 'Niteroi'})
CREATE (f:Funcionario {matricula: 101, nome: 'Ana Lima', cargo: 'Analista', salario: 6500, departamentoCodigo: 10, ativo: true})
CREATE (f:Funcionario {matricula: 102, nome: 'Bruno Costa', cargo: 'Desenvolvedor', salario: 7800, departamentoCodigo: 10, ativo: true})
CREATE (f:Funcionario {matricula: 103, nome: 'Carla Mendes', cargo: 'Contadora', salario: 7200, departamentoCodigo: 20, ativo: true})
CREATE (f:Funcionario {matricula: 104, nome: 'Diego Rocha', cargo: 'Assistente', salario: 3900, departamentoCodigo: 30, ativo: false})
CREATE (f:Funcionario {matricula: 105, nome: 'Elisa Nunes', cargo: 'Analista', salario: 6100, departamentoCodigo: 10, ativo: true})
```

**Por que usamos `departamentoCodigo`?** Porque a versão Cypher v0.5 ainda não permite criar relações com `CREATE (f)-[:TRABALHA_EM]->(d)`. Esse campo é uma solução didática temporária; **não** é uma chave estrangeira com integridade referencial automática.

# Capítulo 6 — Criando nós: CREATE

## 6.1. Inserção simples — [IMPLEMENTADO v0.5]

```cypher
CREATE (f:Funcionario {matricula: 106, nome: 'Fernanda Alves', cargo: 'Estagiaria', salario: 1800, departamentoCodigo: 10})
```

Leia o comando assim: **crie** um nó chamado temporariamente `f`, com o rótulo `Funcionario`, e atribua as propriedades indicadas. A variável `f` serve apenas para a instrução atual.

## 6.2. Criando e retornando um valor

```cypher
CREATE (f:Funcionario {matricula: 107, nome: 'Gabriel Pinto'})
RETURN f.nome
```

A ponte devolve uma linha com o campo `f.nome`.

## 6.3. Tipos simples de propriedades

```cypher
CREATE (p:Produto {codigo: 501, nome: 'Teclado', preco: 149.9, disponivel: true, observacao: null})
```

O interpretador utiliza valores JSON para números, booleanos e `null`, além de textos delimitados por aspas simples. Nem todos os tipos e operações de openCypher são aceitos.

**Exercício 6.1.** Crie três nós `:Produto` com códigos 501, 502 e 503 e preços diferentes.

# Capítulo 7 — Consultando dados: MATCH e RETURN

## 7.1. Listar funcionários — [IMPLEMENTADO v0.5]

```cypher
MATCH (f:Funcionario)
RETURN f.matricula, f.nome, f.cargo
```

Em SQL, uma consulta semelhante seria:

```sql
SELECT matricula, nome, cargo FROM funcionario;
```

## 7.2. Selecionar uma propriedade

```cypher
MATCH (f:Funcionario)
RETURN f.nome
```

## 7.3. Retornar o nó completo

```cypher
MATCH (f:Funcionario)
RETURN f
```

A saída representa o objeto interno do nó, incluindo rótulos e propriedades.

## 7.4. Contar funcionários

```cypher
MATCH (f:Funcionario)
RETURN count(f)
```

**Resultado esperado com os dados iniciais:** `5`.

## 7.5. Identificador interno

```cypher
MATCH (f:Funcionario)
RETURN id(f), f.nome
```

O ID interno é posicional e pode mudar após exclusões. **Use `matricula` como identificador de negócio**, e não `id(f)`.

# Capítulo 8 — Filtrando e limitando resultados

## 8.1. Igualdade em WHERE — [IMPLEMENTADO v0.5]

```cypher
MATCH (f:Funcionario)
WHERE f.cargo = 'Analista'
RETURN f.nome, f.salario
```

**Resultado esperado:** Ana Lima e Elisa Nunes.

## 8.2. Filtro por número

```cypher
MATCH (f:Funcionario)
WHERE f.departamentoCodigo = 10
RETURN f.nome
```

## 8.3. Filtro diretamente no padrão

```cypher
MATCH (f:Funcionario {matricula: 103})
RETURN f.nome, f.cargo
```

## 8.4. Limitar resultados

```cypher
MATCH (f:Funcionario)
RETURN f.nome
LIMIT 3
```

`LIMIT` não implica ordenação. Não dependa da ordem de retorno para definir quais são os “três primeiros” funcionários.

## 8.5. Filtros avançados — [CONCEITUAL / FUTURO]

As consultas abaixo mostram objetivos comuns, **mas não são suportadas pelo executor v0.5**:

```cypher
// Exemplo ilustrativo; NÃO EXECUTAR na v0.5
MATCH (f:Funcionario)
WHERE f.salario > 6000 AND f.ativo = true
RETURN f.nome
ORDER BY f.salario DESC
```

Na versão atual, para esse tipo de operação, obtenha os registros e aplique o filtro/ordenação em Python ou PHP, ou amplie o executor Cypher.

# Capítulo 9 — Alterando e excluindo registros

## 9.1. Atualizar propriedades — [IMPLEMENTADO v0.5]

```cypher
MATCH (f:Funcionario {matricula: 101})
SET f.salario = 6900
```

Depois, consulte:

```cypher
MATCH (f:Funcionario {matricula: 101})
RETURN f.nome, f.salario
```

Na ponte, coloque a atualização em `setup` **depois** dos comandos de criação e use a consulta em `query`.

## 9.2. Alterar mais de uma propriedade

```cypher
MATCH (f:Funcionario {matricula: 104})
SET f.cargo = 'Assistente Administrativo', f.ativo = true
```

## 9.3. Remover uma propriedade

```cypher
MATCH (f:Funcionario {matricula: 104})
REMOVE f.cargo
```

Remover uma propriedade não é o mesmo que excluir o funcionário.

## 9.4. Excluir um nó

```cypher
MATCH (f:Funcionario {matricula: 104})
DELETE f
```

`DELETE` exige que o nó não tenha relacionamentos. A variante `DETACH DELETE` elimina também suas conexões:

```cypher
MATCH (f:Funcionario {matricula: 104})
DETACH DELETE f
```

**Cuidado:** o executor é experimental e não oferece transações ACID. Faça cópias dos dados e nunca utilize esta versão para informações reais sem um mecanismo de persistência, controle de acesso e recuperação.

# Capítulo 10 — Tipos de dados e expressões

## 10.1. Valores reconhecidos pelo interpretador

| Tipo de valor | Exemplo no CREATE | Observação |
|---|---|---|
| Texto | `nome: 'Ana'` | Aspas simples |
| Inteiro | `idade: 29` | JSON numérico |
| Decimal | `salario: 6500.5` | JSON numérico |
| Booleano | `ativo: true` | `true` ou `false` |
| Nulo | `observacao: null` | Valor JSON nulo |

O projeto utiliza `serde_json::Value` internamente. Isso **não significa** que todas as regras de coerção, comparação, datas e funções do openCypher estejam implementadas.

## 10.2. Diferença entre propriedade ausente e nula

Em uma projeção simples, uma propriedade ausente é apresentada como `null`:

```cypher
MATCH (f:Funcionario)
RETURN f.email
```

Isso não demonstra suporte completo às regras de valores nulos da linguagem Cypher.

## 10.3. Expressões não implementadas — [CONCEITUAL / FUTURO]

```cypher
// Apenas sintaxe de referência, NÃO executável na v0.5
MATCH (f:Funcionario)
RETURN f.salario * 1.10 AS salarioReajustado
```

Para calcular reajustes agora, recupere `f.salario` e multiplique por `1.10` no programa Python/PHP.

# Capítulo 11 — Relacionamentos e JOINs

## 11.1. Como o SQL relacionaria os dados

```sql
SELECT f.nome, d.nome AS departamento
FROM funcionario f
INNER JOIN departamento d
  ON d.id = f.departamento_id;
```

## 11.2. Como um grafo expressa o mesmo vínculo

```cypher
// [CONCEITUAL / FUTURO] — NÃO executável no Cypher v0.5
CREATE (f:Funcionario {matricula: 101, nome: 'Ana Lima'})
CREATE (d:Departamento {codigo: 10, nome: 'Tecnologia'})
// Uma futura API de grafo deve criar a aresta TRABALHA_EM
```

Em uma implementação Cypher com relacionamentos, a consulta desejada seria:

```cypher
// [CONCEITUAL / FUTURO]
MATCH (f:Funcionario)-[:TRABALHA_EM]->(d:Departamento)
RETURN f.nome, d.nome
```

**Na extensão v0.5**, a estrutura `PropertyGraph` em Rust consegue armazenar arestas, mas o executor Cypher não aceita esses padrões. Portanto, não confunda capacidade do núcleo Rust com capacidade do interpretador.

## 11.3. Alternativa prática: relacionar dados no Python/PHP

Até que a consulta por arestas seja exposta, é possível consultar funcionários e departamentos separadamente e unir os resultados por `departamentoCodigo` na aplicação. Essa abordagem funciona para exercícios, mas não substitui integridade referencial.

## 11.4. Outros tipos de relacionamento — [CONCEITUAL / FUTURO]

```text
(Funcionario) -[:GERENCIA]-> (Departamento)
(Funcionario) -[:PARTICIPA_DE]-> (Projeto)
(Cliente)     -[:REALIZOU]-> (Pedido)
(Paciente)    -[:ATENDIDO_POR]-> (Medico)
```

**Exercício 11.1.** Desenhe um grafo em papel contendo três funcionários, dois projetos e as relações `PARTICIPA_DE`.

# Capítulo 12 — Funções, agrupamentos e ordenação

## 12.1. COUNT — [IMPLEMENTADO v0.5]

```cypher
MATCH (f:Funcionario {departamentoCodigo: 10})
RETURN count(f)
```

**Resultado esperado:** `3`.

## 12.2. SUM, AVG, MIN e MAX — [CONCEITUAL / FUTURO]

```cypher
// Exemplo de linguagem Cypher, NÃO executável na v0.5
MATCH (f:Funcionario)
RETURN count(f), sum(f.salario), avg(f.salario), min(f.salario), max(f.salario)
```

No conjunto inicial de cinco funcionários, a soma dos salários é **R$ 31.500**, a média é **R$ 6.300**, o mínimo é **R$ 3.900** e o máximo é **R$ 7.800**. Esses valores podem ser calculados no Python/PHP após a consulta.

## 12.3. ORDER BY e DISTINCT — [CONCEITUAL / FUTURO]

```cypher
// NÃO executável na v0.5
MATCH (f:Funcionario)
RETURN DISTINCT f.cargo
ORDER BY f.cargo
```

**Alternativa:** utilize `sorted`, `set` e outras operações nativas em Python, ou `usort` e deduplicação em PHP.

# Capítulo 13 — Integridade, índices, usuários e transações

## 13.1. Chaves e integridade

No Oracle, uma chave primária pode impedir duplicidade e uma chave estrangeira pode assegurar a existência do departamento relacionado. **O executor Cypher v0.5 não fornece esses comandos nem essas garantias.**

Por isso, adote `matricula` e `codigo` como identificadores de negócio e valide a unicidade na aplicação durante os exercícios. Essa validação isolada não resolve concorrência de múltiplos usuários.

## 13.2. Índices

O núcleo Rust possui mecanismos internos de índice de propriedades. Isso não implica disponibilidade de `CREATE INDEX` via Cypher.

```cypher
// [CONCEITUAL / FUTURO] — NÃO executar na v0.5
CREATE INDEX funcionario_matricula FOR (f:Funcionario) ON (f.matricula)
```

## 13.3. Usuários, permissões e papéis

O livro de referência dedica atenção a `GRANT`, privilégios e papéis do Oracle. Na extensão NexusDB examinada, **não existe um equivalente executável de gestão de usuários e privilégios**. Não presuma que instruções SQL como `CREATE USER`, `GRANT` ou `REVOKE` funcionem.

## 13.4. Transações

O executor `cypher::execute` modifica um grafo em memória e sua documentação explicita que **não é transacional**. A ponte JSON permite executar comandos preparatórios, mas isso não é uma transação ACID. `BEGIN`, `COMMIT` e `ROLLBACK` não estão implementados como comandos de banco.

## 13.5. Segurança mínima para protótipos

Nunca concatene entrada externa não confiável em instruções Cypher. A ponte atual não oferece parâmetros de consulta. Não exponha o executável à internet; execute-o em ambiente controlado e com dados fictícios.

# Capítulo 14 — Usando NexusDB com Python

## 14.1. Comunicação pelo processo Rust

O código abaixo não usa um driver de banco. Ele executa o `tck_bridge`, envia JSON pela entrada padrão e recebe JSON pela saída padrão.

Salve como `exemplo_empresa.py`:

```python
import json
import subprocess
import sys

BRIDGE = sys.argv[1] if len(sys.argv) > 1 else "./target/release/tck_bridge"

BASE = [
    "CREATE (d:Departamento {codigo: 10, nome: 'Tecnologia', cidade: 'Niteroi'})",
    "CREATE (d:Departamento {codigo: 20, nome: 'Financeiro', cidade: 'Rio de Janeiro'})",
    "CREATE (d:Departamento {codigo: 30, nome: 'Recursos Humanos', cidade: 'Niteroi'})",
    "CREATE (f:Funcionario {matricula: 101, nome: 'Ana Lima', cargo: 'Analista', salario: 6500, departamentoCodigo: 10, ativo: true})",
    "CREATE (f:Funcionario {matricula: 102, nome: 'Bruno Costa', cargo: 'Desenvolvedor', salario: 7800, departamentoCodigo: 10, ativo: true})",
    "CREATE (f:Funcionario {matricula: 103, nome: 'Carla Mendes', cargo: 'Contadora', salario: 7200, departamentoCodigo: 20, ativo: true})",
    "CREATE (f:Funcionario {matricula: 104, nome: 'Diego Rocha', cargo: 'Assistente', salario: 3900, departamentoCodigo: 30, ativo: false})",
    "CREATE (f:Funcionario {matricula: 105, nome: 'Elisa Nunes', cargo: 'Analista', salario: 6100, departamentoCodigo: 10, ativo: true})",
]

def consultar(query, setup=None):
    pedido = {"setup": BASE if setup is None else setup, "query": query}
    processo = subprocess.run(
        [BRIDGE], input=json.dumps(pedido), text=True,
        capture_output=True, check=True, timeout=30
    )
    resposta = json.loads(processo.stdout)
    if not resposta.get("ok"):
        raise RuntimeError(f"{resposta.get('stage')}: {resposta.get('error')}")
    return resposta["rows"]

funcionarios = consultar(
    "MATCH (f:Funcionario) RETURN f.matricula, f.nome, f.salario, f.departamentoCodigo"
)
for f in funcionarios:
    print(f["f.matricula"], f["f.nome"], f["f.salario"])

salarios = [f["f.salario"] for f in funcionarios]
print("Total:", sum(salarios))
print("Média:", sum(salarios) / len(salarios))

por_codigo = {
    d["d.codigo"]: d["d.nome"]
    for d in consultar("MATCH (d:Departamento) RETURN d.codigo, d.nome")
}
for f in funcionarios:
    print(f["f.nome"], "->", por_codigo.get(f["f.departamentoCodigo"], "Desconhecido"))

# Atualização seguida de consulta NA MESMA requisição JSON.
atualizados = consultar(
    "MATCH (f:Funcionario {matricula: 101}) RETURN f.nome, f.salario",
    setup=BASE + ["MATCH (f:Funcionario {matricula: 101}) SET f.salario = 6900"]
)
print("Após reajuste:", atualizados)
```

Execução no Windows:

```powershell
python exemplo_empresa.py .\target\release\tck_bridge.exe
```

Execução no Linux/macOS:

```bash
python3 exemplo_empresa.py ./target/release/tck_bridge
```

## 14.2. Por que reenviamos BASE?

Porque cada execução da ponte inicia um grafo vazio. A variável `BASE` é um conjunto de instruções preparatórias, **não** um mecanismo de persistência. Em uma aplicação real, seria necessário integrar um serviço persistente.

## 14.3. Evite consultas montadas com entrada do usuário

```python
# NÃO faça isto com dados externos:
# query = "MATCH (f:Funcionario) WHERE f.nome = '" + nome_usuario + "' RETURN f.nome"
```

A ponte não suporta parâmetros seguros. Em exercícios, mantenha as consultas fixas e os dados simulados.

# Capítulo 15 — Usando NexusDB com PHP

## 15.1. Uma chamada simples

O PHP também pode enviar um JSON para o executável Rust usando `proc_open()`. Salve como `exemplo_empresa.php`:

```php
<?php
$bridge = $argv[1] ?? './target/release/tck_bridge';

$base = [
    "CREATE (d:Departamento {codigo: 10, nome: 'Tecnologia', cidade: 'Niteroi'})",
    "CREATE (d:Departamento {codigo: 20, nome: 'Financeiro', cidade: 'Rio de Janeiro'})",
    "CREATE (d:Departamento {codigo: 30, nome: 'Recursos Humanos', cidade: 'Niteroi'})",
    "CREATE (f:Funcionario {matricula: 101, nome: 'Ana Lima', cargo: 'Analista', salario: 6500, departamentoCodigo: 10})",
    "CREATE (f:Funcionario {matricula: 102, nome: 'Bruno Costa', cargo: 'Desenvolvedor', salario: 7800, departamentoCodigo: 10})",
    "CREATE (f:Funcionario {matricula: 103, nome: 'Carla Mendes', cargo: 'Contadora', salario: 7200, departamentoCodigo: 20})",
    "CREATE (f:Funcionario {matricula: 104, nome: 'Diego Rocha', cargo: 'Assistente', salario: 3900, departamentoCodigo: 30})",
    "CREATE (f:Funcionario {matricula: 105, nome: 'Elisa Nunes', cargo: 'Analista', salario: 6100, departamentoCodigo: 10})",
];

function consultar(string $bridge, array $setup, string $query): array {
    $descritores = [
        0 => ['pipe', 'r'],
        1 => ['pipe', 'w'],
        2 => ['pipe', 'w'],
    ];
    $processo = proc_open([$bridge], $descritores, $pipes);
    if (!is_resource($processo)) {
        throw new RuntimeException('Falha ao iniciar tck_bridge');
    }
    fwrite($pipes[0], json_encode(
        ['setup' => $setup, 'query' => $query], JSON_UNESCAPED_UNICODE
    ));
    fclose($pipes[0]);
    $saida = stream_get_contents($pipes[1]);
    fclose($pipes[1]);
    $erro = stream_get_contents($pipes[2]);
    fclose($pipes[2]);
    $codigo = proc_close($processo);
    if ($codigo !== 0) {
        throw new RuntimeException('Falha na ponte: ' . $erro);
    }
    $resposta = json_decode($saida, true, 512, JSON_THROW_ON_ERROR);
    if (empty($resposta['ok'])) {
        throw new RuntimeException(($resposta['stage'] ?? 'query') . ': ' . ($resposta['error'] ?? 'Erro'));
    }
    return $resposta['rows'];
}

$linhas = consultar($bridge, $base,
    'MATCH (f:Funcionario) RETURN f.nome, f.salario, f.departamentoCodigo');

$total = 0;
foreach ($linhas as $linha) {
    echo $linha['f.nome'] . ': R$ ' . $linha['f.salario'] . PHP_EOL;
    $total += $linha['f.salario'];
}
echo 'Total: R$ ' . $total . PHP_EOL;
echo 'Média: R$ ' . ($total / count($linhas)) . PHP_EOL;

$alterado = consultar($bridge,
    array_merge($base, ["MATCH (f:Funcionario {matricula: 101}) SET f.salario = 6900"]),
    'MATCH (f:Funcionario {matricula: 101}) RETURN f.nome, f.salario'
);
print_r($alterado);
```

Windows:

```powershell
php exemplo_empresa.php .\target\release\tck_bridge.exe
```

Linux/macOS:

```bash
php exemplo_empresa.php ./target/release/tck_bridge
```

**Observações:** `proc_open` precisa estar habilitado e o executável deve existir. Este exemplo é apropriado para execução local em linha de comando, não para receber consultas arbitrárias de visitantes de um site.

# Capítulo 16 — Algoritmos de grafos e aplicações

O núcleo Rust da extensão disponibiliza algoritmos e estruturas de grafos, mas eles **não são expostos como comandos Cypher pela ponte v0.5**.

| Recurso no núcleo Rust | O que resolve | Exemplo de aplicação | Disponível via ponte Cypher v0.5? |
|---|---|---|---|
| BFS | Busca em largura | Encontrar conexões em poucos passos | Não |
| Dijkstra | Menor caminho com pesos não negativos | Rotas entre unidades | Não |
| PageRank | Importância estrutural | Identificar entidades influentes | Não |
| CSR | Armazenamento compacto de adjacências | Processar grafos maiores | Não |
| SpMV / semianéis | Operações matriciais sobre grafos | Análises algébricas | Não |
| Rayon | Paralelismo em CPU | Acelerar operações selecionadas | Não configurável pela ponte |

**GPU:** a presença de uma opção `Cuda` na API não prova que exista um backend CUDA operacional neste pacote. O uso de GPU, cache de VRAM e escalonamento por recursos deve ser documentado e validado separadamente no projeto NexusDB principal.

## 16.1. Onde usar grafos?

- **Hospital:** pacientes, profissionais, leitos e procedimentos; exige segurança, privacidade e persistência antes de qualquer uso real.
- **Logística:** centros de distribuição, rotas e entregas.
- **Recursos humanos:** colaboradores, equipes, competências e projetos.
- **Tecnologia:** dependências entre serviços, servidores e aplicações.

# Capítulo 17 — Projeto guiado e exercícios

## 17.1. Projeto: cadastro e relatório de funcionários

**Objetivo:** construir um relatório local que liste funcionários, departamento e salário, sem banco persistente.

**Etapa A — Cadastrar.** Utilize o `BASE` do capítulo 14 ou 15.

**Etapa B — Consultar.** Execute:

```cypher
MATCH (f:Funcionario)
RETURN f.matricula, f.nome, f.salario, f.departamentoCodigo
```

**Etapa C — Associar departamentos.** Consulte os nós `Departamento` e associe os dados em Python/PHP pelo código.

**Etapa D — Calcular.** Na linguagem de aplicação, calcule total, média, maior e menor salário.

**Etapa E — Atualizar.** Reenvie a base com uma instrução `SET` no final de `setup` e consulte o funcionário alterado.

## 17.2. Lista de exercícios

1. Cadastre dois novos funcionários e consulte seus nomes.
2. Conte quantos funcionários existem após os novos cadastros.
3. Liste os funcionários do departamento 10.
4. Localize a matrícula 103 por padrão de propriedades.
5. Atualize o salário da matrícula 105 para 6400.
6. Remova a propriedade `cargo` da matrícula 104.
7. Exclua a matrícula 104 e conte os funcionários restantes.
8. Calcule em Python/PHP o salário médio por departamento.
9. Ordene em Python/PHP os funcionários por salário decrescente.
10. Explique por que o `id(f)` não deve substituir a matrícula.
11. Desenhe o grafo ideal de funcionários e departamentos usando `TRABALHA_EM`.
12. Explique por que uma consulta com `JOIN` não pode ser simplesmente colada no executor Cypher atual.

## 17.3. Respostas orientativas

- Exercício 2: a contagem deve aumentar de 5 para 7 quando dois novos nós forem incluídos em `setup`.
- Exercício 3: `MATCH (f:Funcionario {departamentoCodigo: 10}) RETURN f.nome`.
- Exercício 4: `MATCH (f:Funcionario {matricula: 103}) RETURN f.nome`.
- Exercício 5: `MATCH (f:Funcionario {matricula: 105}) SET f.salario = 6400`.
- Exercício 6: `MATCH (f:Funcionario {matricula: 104}) REMOVE f.cargo`.
- Exercício 7: `MATCH (f:Funcionario {matricula: 104}) DELETE f`; após a exclusão, a contagem da base original é 4.
- Exercício 8: agrupe registros pelo campo `departamentoCodigo` na aplicação; a versão atual não implementa `GROUP BY`/agregações gerais via Cypher.

# Capítulo 18 — Referência rápida e solução de problemas

## 18.1. Guia de comandos executáveis

| Objetivo | Forma geral |
|---|---|
| Criar nó | `CREATE (n:Rotulo {campo: valor})` |
| Listar nós | `MATCH (n:Rotulo) RETURN n` |
| Listar propriedades | `MATCH (n:Rotulo) RETURN n.campo` |
| Filtrar por igualdade | `MATCH (n:Rotulo) WHERE n.campo = valor RETURN n` |
| Filtrar no padrão | `MATCH (n:Rotulo {campo: valor}) RETURN n` |
| Contar | `MATCH (n:Rotulo) RETURN count(n)` |
| Limitar | `MATCH (n:Rotulo) RETURN n.campo LIMIT 5` |
| Atualizar | `MATCH (n:Rotulo {id: 1}) SET n.campo = valor` |
| Remover propriedade | `MATCH (n:Rotulo {id: 1}) REMOVE n.campo` |
| Excluir nó desconectado | `MATCH (n:Rotulo {id: 1}) DELETE n` |
| Excluir nó e conexões | `MATCH (n:Rotulo {id: 1}) DETACH DELETE n` |

## 18.2. Erros frequentes

**“unsupported or malformed Cypher query”.** Verifique se o comando está na lista acima. Não use `ORDER BY`, relações em `MATCH`, `MERGE`, filtros compostos ou funções não implementadas.

**“Os dados sumiram”.** A ponte inicia um novo grafo em cada chamada. Reenvie os comandos em `setup`.

**“Não consigo executar tck_bridge”.** Compile com `cargo build --release --bin tck_bridge`, confirme o caminho e verifique permissões.

**“DELETE requires disconnected nodes”.** O nó possui relações; `DELETE` não pode removê-lo sem antes tratar as arestas. `DETACH DELETE` remove as conexões também.

**“O código Python/PHP não encontra as colunas”.** A resposta utiliza nomes como `f.nome` e `f.salario` como chaves JSON. Consulte `rows` e confira as chaves recebidas.

**“A contagem não corresponde ao esperado”.** Confirme o conteúdo do `setup`, especialmente alterações ou exclusões aplicadas antes de `query`.

## 18.3. Antes de desenvolver um sistema real

É necessário evoluir a extensão para disponibilizar persistência, recuperação de falhas, IDs estáveis, transações, controle de concorrência, autenticação, autorização, parâmetros de consulta, API de serviço e observabilidade. Os recursos descritos neste livro servem para aprendizagem e prototipação controlada.

---

# Referências e notas editoriais

1. GONÇALVES, Eduardo. *SQL — Uma abordagem para banco de dados Oracle*. Casa do Código. Obra anexada pelo usuário, utilizada **somente como referência de organização didática e seleção de assuntos**, não como fonte de reprodução textual.
2. **NexusDB Graph Extension v0.5 TCK**. Código-fonte fornecido no projeto, especialmente `src/cypher.rs`, `src/lib.rs`, `src/bin/tck_bridge.rs` e `README.md`.
3. **openCypher 9**. Documento de referência da linguagem fornecido no projeto. A sintaxe completa descrita nele não deve ser confundida com a cobertura da extensão v0.5.
4. **Cypher Style Guide** e gramática `Cypher.g4`, fornecidos no projeto como referências de sintaxe e estilo.

**Nota de validação:** os exemplos foram revisados por inspeção estática do interpretador e da ponte Rust. Não houve execução de `cargo test` ou dos programas Python/PHP neste ambiente. Os resultados numéricos foram calculados sobre o conjunto didático definido no capítulo 5.

**Fim da edição 1.0.**
