# OpenFlights → NexusDB

Importador preparado para transformar os arquivos `.dat` fornecidos em um **property graph** para demonstrações do NexusDB.

## Modelo do grafo

```text
                         ┌───────────────┐
                         │    Country    │
                         └──────▲──▲─────┘
                                │  │
                      LOCATED_IN│  │BASED_IN
                                │  │
┌─────────┐ DEPARTURE ┌────────┴─┐│   OPERATES  ┌─────────┐
│ Airport │──────────►│   Route   │◄─────────────│ Airline │
└─────────┘            └────┬─────┘              └─────────┘
     ▲                      │
     │ ARRIVAL              │ USES_AIRCRAFT
     │                      ▼
     └────────────────  AircraftType
```

Cada linha de `routes.dat` vira um nó `Route`. Essa escolha é deliberada: torna simples demonstrar **impacto de fechamento de aeroporto, cancelamento de rota, indisponibilidade de companhia, aeronaves utilizadas, caminhos e centralidade**.

## Arquivos usados

- `airports-extended.dat` — padrão, por ser um superset do `airports.dat`.
- `airlines.dat`
- `routes.dat`
- `countries.dat`
- `planes.dat`

`airports.dat` também é suportado com `--use-basic-airports`.

`alsearch.htm` não é necessário para a importação; é uma página de busca/interface, não um arquivo de entidades do grafo.

## 1. Teste sem gravar

No Windows/PowerShell:

```powershell
python import_openflights_nexusdb.py `
  --folder "C:\CAMINHO\openflights" `
  --password "SUA_SENHA" `
  --dry-run
```

## 2. Teste pequeno no NexusDB

```powershell
python import_openflights_nexusdb.py `
  --folder "C:\CAMINHO\openflights" `
  --url http://127.0.0.1:7475 `
  --user admin `
  --password "SUA_SENHA" `
  --database OPENFLIGHTS_TEST `
  --route-limit 1000
```

## 3. Importação completa

```powershell
python import_openflights_nexusdb.py `
  --folder "C:\CAMINHO\openflights" `
  --url http://127.0.0.1:7475 `
  --user admin `
  --password "SUA_SENHA" `
  --database OPENFLIGHTS_GRAPH
```

O importador usa `/db/data/node/bulk` e `/db/data/relationship/bulk`, portanto é muito mais adequado ao volume deste dataset do que criar um nó por requisição.

## Consultas para validar

```cypher
MATCH (a:Airport) RETURN a.airport_id, a.name, a.city, a.country, a.iata LIMIT 20
```

```cypher
MATCH (a:Airline) RETURN a.airline_id, a.name, a.country, a.active LIMIT 20
```

```cypher
MATCH (a:Airport)-[:DEPARTURE]->(r:Route)
RETURN a.name, a.iata, r.route_key, r.airline_code LIMIT 20
```

```cypher
CALL DB.STATS()
```

## Próxima aplicação

O dataset já fica preparado para uma aplicação **NexusDB AirRoute Resilience**, com:

- seleção de aeroporto, companhia ou rota;
- simulação de indisponibilidade;
- rotas e aeroportos afetados;
- companhias afetadas;
- aeronaves/equipamentos envolvidos;
- caminhos alternativos;
- Degree Centrality / PageRank / Connected Components;
- mapa geográfico usando latitude/longitude;
- Risk Score de conectividade.

### Observação

Uma rota do OpenFlights representa conectividade declarada no dataset, não frequência, assentos disponíveis, horário, preço ou capacidade operacional em tempo real. Esses fatores podem ser incorporados depois como novas propriedades/datasets.
