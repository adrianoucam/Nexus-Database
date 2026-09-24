import json
import urllib.request
import urllib.error


class NexusClient:
    def __init__(self, base_url, user, password, database):
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.password = password
        self.database = database

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "X-User": self.user,
            "X-Pass": self.password,
            "X-Database": self.database,
        }

    def cypher(self, query):
        data = json.dumps(
            {"statements": [{"query": query}]},
            ensure_ascii=False,
        ).encode("utf-8")

        req = urllib.request.Request(
            self.base_url + "/db/data/cypher",
            data=data,
            method="POST",
            headers=self._headers(),
        )

        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                raw = response.read().decode("utf-8", "replace")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Falha conectando a {self.base_url}: {exc}") from exc

    def authenticate_once(self):
        """Uma única tentativa antes das consultas de carga."""
        payload = self.cypher("CALL DB.STATS()")
        if not isinstance(payload, dict):
            raise RuntimeError("Resposta inválida do NexusDB.")

        errors = payload.get("errors")
        if errors:
            raise RuntimeError(f"Pré-autenticação falhou: {errors}")

        if payload.get("status") in ("error", "failed"):
            raise RuntimeError(payload.get("error") or "Falha na autenticação.")

        return payload

    def cluster_status(self):
        try:
            with urllib.request.urlopen(
                self.base_url + "/cluster/status", timeout=10
            ) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except Exception:
            return {}

    @staticmethod
    def _dict_rows_to_table(rows):
        if not isinstance(rows, list):
            return [], []

        dict_rows = [row for row in rows if isinstance(row, dict)]
        if not dict_rows:
            return [], []

        columns = []
        seen = set()
        for row in dict_rows:
            for key in row.keys():
                if key not in seen:
                    seen.add(key)
                    columns.append(str(key))

        normalized = [
            [row.get(column) for column in columns]
            for row in dict_rows
        ]
        return columns, normalized

    @staticmethod
    def _table_from_payload(payload):
        """Reconhece primeiro o formato nativo atual do NexusDB."""
        if not isinstance(payload, dict):
            return [], []

        # FORMATO NATIVO NEXUSDB:
        # {"status":"success", "processados":N,
        #  "resultados":[{"s.name":"...", "p.product_id":"..."}, ...]}
        resultados = payload.get("resultados")
        if isinstance(resultados, list):
            if resultados == []:
                return [], []

            cols, rows = NexusClient._dict_rows_to_table(resultados)
            if cols:
                return cols, rows

            if all(isinstance(item, list) for item in resultados):
                width = max((len(item) for item in resultados), default=0)
                return [f"col_{i+1}" for i in range(width)], resultados

        # Compatibilidade com formatos tabulares experimentais.
        candidates = [payload]
        for key in ("results", "result", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates.extend(
                    item for item in value if isinstance(item, dict)
                )
            elif isinstance(value, dict):
                candidates.append(value)

        for obj in candidates:
            cols = obj.get("columns") or obj.get("headers") or obj.get("fields")
            rows = obj.get("rows") or obj.get("data") or obj.get("records") or obj.get("values")

            if not isinstance(cols, list) or not isinstance(rows, list):
                continue

            normalized = []
            for item in rows:
                if isinstance(item, dict) and isinstance(item.get("row"), list):
                    normalized.append(item["row"])
                elif isinstance(item, dict) and isinstance(item.get("values"), list):
                    normalized.append(item["values"])
                elif isinstance(item, list):
                    normalized.append(item)
                elif isinstance(item, dict):
                    normalized.append([item.get(c) for c in cols])

            if normalized or rows == []:
                return [str(c) for c in cols], normalized

        # Neo4j-like.
        results = payload.get("results")
        if isinstance(results, list) and results:
            r0 = results[0]
            if isinstance(r0, dict):
                cols = r0.get("columns", [])
                data = r0.get("data", [])
                if isinstance(cols, list) and isinstance(data, list):
                    rows = [
                        item.get("row", [])
                        for item in data
                        if isinstance(item, dict)
                    ]
                    return [str(c) for c in cols], rows

        return [], []

    def query_rows(self, query):
        payload = self.cypher(query)

        if not isinstance(payload, dict):
            raise RuntimeError(
                f"Resposta JSON inesperada do NexusDB: {type(payload).__name__}"
            )

        errors = payload.get("errors")
        if errors:
            raise RuntimeError(f"Cypher falhou: {errors}\nQuery: {query}")

        if payload.get("status") in ("error", "failed"):
            raise RuntimeError(
                f"NexusDB retornou erro: {payload.get('error')}\nQuery: {query}"
            )

        cols, rows = self._table_from_payload(payload)

        # Consulta válida com zero registros.
        if not cols and payload.get("processados") == 0:
            return [], [], payload

        if not cols:
            raise RuntimeError(
                "O NexusDB respondeu, mas o campo nativo 'resultados' "
                "não pôde ser convertido. Consulte o JSON bruto."
            )

        return cols, rows, payload
