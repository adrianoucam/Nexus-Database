# AGENTS.md — Examples

## Scope

Applies to all example applications, demos, benchmarks and tutorial code.

## Safety

Examples must never assume access to production databases.

Use dedicated names such as:

```text
ACADEMICO_DEMO
ACADEMICO_TEST
EXAMPLE_*
```

Do not target user databases such as biomedical, production or personal datasets unless explicitly requested.

## Credentials

Examples must:

- read passwords from environment or secure prompt;
- never commit real passwords;
- never render passwords into browser HTML;
- avoid repeated invalid authentication attempts.

## Database creation

If an example can create a database, creation must be explicit.

Do not silently delete an existing database.

## Reproducibility

Document:

```text
requirements
commands
expected database name
expected data size
expected output
known limitations
```

## Bulk examples

Use bulk endpoints when demonstrating large insertion.

Do not teach one-request-per-row patterns unless the point is explicitly to benchmark the anti-pattern.

## Agent/LLM examples

The LLM must not be the source of database facts.

Preferred flow:

```text
LLM/agent
  ↓
structured NexusDB tool
  ↓
native database result
  ↓
LLM explanation
```

## Spatial examples

State coordinate units.

Do not call a degree-based radius "meters".

## Graph examples

Explain that centrality and paths are structural measures.

Do not interpret PageRank as business importance without domain justification.

## Cleanup

Tests/examples that start a temporary NexusDB instance must stop only that instance.

Never stop the user's installed service as cleanup.

## Output

Examples should surface clear diagnostics for:

```text
HTTP status
error code
database
operation
elapsed time
```

without exposing credentials.
