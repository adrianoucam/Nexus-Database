#!/usr/bin/env python3
"""NexusDB Backup: online SQLite snapshots and transactional journal recovery.

Python 3.10+, standard library only. See README.md for guarantees and limits.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.request
import uuid
import zipfile

VERSION = 1
COLUMNS = {
    "nodes": ("id", "label", "properties", "created_at", "updated_at"),
    "relationships": ("id", "node_a", "node_b", "rel_type", "properties", "created_at", "updated_at"),
}


class BackupError(Exception):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def database_name(value):
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", value) or value in (".", ".."):
        raise BackupError("Nome de banco inválido")
    return value


def utc_ms(value):
    try:
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Informe o fuso: Z ou -03:00")
        return int(stamp.timestamp() * 1000)
    except ValueError as e:
        raise BackupError(f"Instante inválido: {e}") from e


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).isoformat(timespec="milliseconds")


@contextlib.contextmanager
def repository_lock(repo):
    repo.mkdir(parents=True, exist_ok=True)
    lock = repo / ".writer.lock"
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as e:
        raise BackupError(f"Repositório em uso: {lock}. Após falha de processo, confirme que ele encerrou antes de remover o lock.") from e
    try:
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()


def connect_read(path):
    if not path.is_file():
        raise BackupError(f"SQLite não encontrado: {path}")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def schema_hash(conn):
    rows = conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' AND name NOT LIKE 'recovery_%' ORDER BY type,name").fetchall()
    return hashlib.sha256(canonical([list(r) for r in rows])).hexdigest()


def journal_info(conn):
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name='recovery_control' AND type='table'").fetchone()
    if not exists:
        return None
    control = conn.execute("SELECT epoch,active_tx,version,initialized_ms FROM recovery_control WHERE singleton=1").fetchone()
    if not control or control[1] is not None or control[2] != VERSION:
        raise BackupError("Diário de recuperação incompleto ou versão incompatível")
    triggers = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name IN ('recovery_nodes_insert','recovery_nodes_update','recovery_nodes_delete','recovery_rels_insert','recovery_rels_update','recovery_rels_delete')").fetchone()[0]
    if triggers != 6:
        raise BackupError("Triggers de recuperação ausentes; não é seguro continuar")
    if conn.execute("SELECT count(*) FROM recovery_transactions WHERE committed_ms IS NULL").fetchone()[0]:
        raise BackupError("Transação de recuperação sem finalização")
    end, stamp = conn.execute("SELECT coalesce(max(id),0),coalesce(max(committed_ms),0) FROM recovery_transactions").fetchone()
    return {"epoch": control[0], "end_tx": end, "covered_ms": stamp or control[3]}


def integrity(conn):
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise BackupError("SQLite falhou no integrity_check")
    if conn.execute("PRAGMA foreign_key_check").fetchone():
        raise BackupError("Relacionamentos com referências inválidas")


def flush_source(url, user, password_env, database):
    password = os.environ.get(password_env) or getpass.getpass("Senha NexusDB: ")
    request = urllib.request.Request(url.rstrip("/") + "/db/admin/flush",
        data=canonical({"database": database}), method="POST",
        headers={"Content-Type": "application/json", "X-User": user, "X-Pass": password, "X-Database": database})
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)
    if result.get("status") != "success":
        raise BackupError("Servidor não confirmou o flush")


def manifest(path):
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("manifest.json")
        if info.file_size > 1024 * 1024:
            raise BackupError("Manifest muito grande")
        m = json.loads(archive.read(info))
    if m.get("format") != VERSION or m.get("kind") not in ("full", "incremental"):
        raise BackupError(f"Formato de backup inválido: {path.name}")
    if not re.fullmatch(r"[0-9a-f]{32}", m.get("id", "")) or path.name != m["id"] + ".nxb":
        raise BackupError("Identidade do pacote inválida")
    database_name(m["database"])
    return m


def catalog(repo):
    result = {}
    if not repo.is_dir():
        raise BackupError(f"Repositório não encontrado: {repo}")
    for path in repo.glob("*.nxb"):
        m = manifest(path)
        result[m["id"]] = (path, m)
    return result


def chain(repo, backup_id):
    entries = catalog(repo)
    result, seen = [], set()
    current = backup_id
    while current:
        if current in seen or current not in entries:
            raise BackupError("Cadeia cíclica ou backup ancestral ausente")
        seen.add(current)
        path, m = entries[current]
        result.append((path, m))
        current = m.get("parent")
    result.reverse()
    if not result or result[0][1]["kind"] != "full":
        raise BackupError("Cadeia sem backup completo")
    for (prior_path, prior), (_, item) in zip(result, result[1:]):
        if item["kind"] != "incremental" or item["parent_sha256"] != digest(prior_path):
            raise BackupError("Ancestral alterado ou encadeamento inválido")
        for key in ("database", "epoch", "schema_sha256"):
            if item[key] != prior[key]:
                raise BackupError(f"Cadeia incompatível: {key}")
        if item["start_tx"] != prior["end_tx"] or item["end_tx"] < item["start_tx"] or item["covered_ms"] < prior["covered_ms"]:
            raise BackupError("Lacuna ou regressão na cadeia")
    return result


def verify_package(path, m):
    filename = "database.sqlite" if m["kind"] == "full" else "transactions.jsonl"
    with zipfile.ZipFile(path) as archive:
        if sorted(archive.namelist()) != sorted(["manifest.json", filename]):
            raise BackupError("Conteúdo inesperado ou duplicado no pacote")
        h, size = hashlib.sha256(), 0
        with archive.open(filename) as src:
            for chunk in iter(lambda: src.read(1024 * 1024), b""):
                h.update(chunk)
                size += len(chunk)
        if h.hexdigest() != m["payload_sha256"] or size != m["payload_bytes"]:
            raise BackupError(f"Checksum incorreto: {path.name}")


def publish(repo, m, payload, filename):
    m["payload_sha256"], m["payload_bytes"] = digest(payload), payload.stat().st_size
    target = repo / (m["id"] + ".nxb")
    temporary = repo / (m["id"] + ".partial")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("manifest.json", canonical(m))
            archive.write(payload, filename)
        with open(temporary, "r+b") as f:
            os.fsync(f.fileno())
        # Unique random name, under the exclusive repository writer lock.
        if target.exists():
            raise BackupError("ID de backup já existe")
        temporary.rename(target)
    finally:
        temporary.unlink(missing_ok=True)
    return m


def backup(repo, source, database, kind, parent_id=None, offline=False, flushed=False):
    repo, source = Path(repo).resolve(), Path(source).resolve()
    database_name(database)
    if repo == source.parent or source.parent in repo.parents:
        raise BackupError("Repositório deve ficar fora da pasta do banco")
    with repository_lock(repo), tempfile.TemporaryDirectory(prefix="nexus-backup-") as work:
        temp = Path(work)
        m = {"format": VERSION, "id": uuid.uuid4().hex, "kind": kind,
             "database": database, "created_ms": time.time_ns() // 1_000_000,
             "parent": None, "start_tx": 0}
        with contextlib.closing(connect_read(source)) as conn:
            conn.execute("BEGIN")
            # First read pins the SQLite snapshot (including committed WAL).
            info = journal_info(conn)
            if kind == "full":
                if not info and not (offline or flushed):
                    raise BackupError("Sem diário: use --flush-url para backup online ou --offline com servidor parado")
                payload = temp / "database.sqlite"
                with contextlib.closing(sqlite3.connect(payload)) as dest:
                    conn.backup(dest, pages=256, sleep=.05)
                    integrity(dest)
                    m["schema_sha256"] = schema_hash(dest)
                    m["nodes"] = dest.execute("SELECT count(*) FROM nodes").fetchone()[0]
                    m["relationships"] = dest.execute("SELECT count(*) FROM relationships").fetchone()[0]
                m.update(info or {"epoch": None, "end_tx": 0, "covered_ms": m["created_ms"]})
                return publish(repo, m, payload, "database.sqlite")
            if not info:
                raise BackupError("Incremental exige NEXUSDB_RECOVERY_JOURNAL=1 e um backup completo inicial")
            prior_chain = chain(repo, parent_id)
            for path, item in prior_chain:
                verify_package(path, item)
            prior_path, prior = prior_chain[-1]
            if prior["database"] != database or prior["epoch"] != info["epoch"] or prior["schema_sha256"] != schema_hash(conn):
                raise BackupError("Banco recriado, restaurado, schema alterado ou origem diferente: faça um novo full")
            if info["end_tx"] < prior["end_tx"]:
                raise BackupError("Histórico de origem regrediu")
            payload = temp / "transactions.jsonl"
            expected = prior["end_tx"] + 1
            previous_time = prior["covered_ms"]
            with open(payload, "wb") as out:
                for row in conn.execute("SELECT id,committed_ms,event_count FROM recovery_transactions WHERE id>? ORDER BY id", (prior["end_tx"],)):
                    events = [dict(e) for e in conn.execute("SELECT seq,entity,operation,row_id,data FROM recovery_events WHERE tx_id=? ORDER BY seq", (row[0],))]
                    if row[0] != expected or row[1] <= previous_time or len(events) != row[2]:
                        raise BackupError("Histórico de transações incompleto ou fora de ordem")
                    out.write(canonical({"id": row[0], "committed_ms": row[1], "events": events}) + b"\n")
                    expected, previous_time = row[0] + 1, row[1]
            if expected != info["end_tx"] + 1:
                raise BackupError("Histórico removido da origem")
            m.update(info)
            m.update(parent=parent_id, parent_sha256=digest(prior_path), start_tx=prior["end_tx"], schema_sha256=prior["schema_sha256"])
            return publish(repo, m, payload, "transactions.jsonl")


def apply_event(conn, event):
    entity, operation = event["entity"], event["operation"]
    if entity not in COLUMNS or operation not in ("upsert", "delete"):
        raise BackupError("Evento de recuperação desconhecido")
    if operation == "delete":
        conn.execute(f'DELETE FROM "{entity}" WHERE id=?', (event["row_id"],))
        return
    row = json.loads(event["data"])
    columns = COLUMNS[entity]
    if set(row) != set(columns) or row["id"] != event["row_id"]:
        raise BackupError("Payload de recuperação inválido")
    updates = ",".join(f'{c}=excluded.{c}' for c in columns if c != "id")
    conn.execute(f'INSERT INTO "{entity}" ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)}) ON CONFLICT(id) DO UPDATE SET {updates}', tuple(row[c] for c in columns))


def materialize(repo, backup_id, output, at_ms=None):
    entries = chain(Path(repo), backup_id)
    for path, m in entries:
        verify_package(path, m)
    base, last = entries[0][1], entries[-1][1]
    if at_ms is not None:
        if not base["epoch"]:
            raise BackupError("Este full não possui diário para PITR")
        if not base["covered_ms"] <= at_ms <= last["covered_ms"]:
            raise BackupError(f"Instante fora da cobertura arquivada: {iso(base['covered_ms'])} até {iso(last['covered_ms'])}")
    with zipfile.ZipFile(entries[0][0]) as archive, archive.open("database.sqlite") as src, open(output, "xb") as dest:
        shutil.copyfileobj(src, dest, 1024 * 1024)
    applied = base["end_tx"]
    with contextlib.closing(sqlite3.connect(output)) as conn:
        integrity(conn)
        if schema_hash(conn) != base["schema_sha256"]:
            raise BackupError("Schema não corresponde ao manifest")
        journal = journal_info(conn)
        if journal and any(journal[k] != base[k] for k in ("epoch", "end_tx", "covered_ms")):
            raise BackupError("Diário não corresponde ao manifest do backup completo")
        conn.execute("PRAGMA journal_mode=DELETE")
        # Replaying into a private staging DB. Source files are never modified.
        for trigger in ("recovery_nodes_insert", "recovery_nodes_update", "recovery_nodes_delete", "recovery_rels_insert", "recovery_rels_update", "recovery_rels_delete"):
            conn.execute(f'DROP TRIGGER IF EXISTS "{trigger}"')
        previous_time = base["covered_ms"]
        for path, m in entries[1:]:
            expected = m["start_tx"] + 1
            with zipfile.ZipFile(path) as archive, archive.open("transactions.jsonl") as stream:
                for line in stream:
                    tx = json.loads(line)
                    if tx["id"] != expected or tx["committed_ms"] <= previous_time:
                        raise BackupError("Transações fora de sequência")
                    previous_time = tx["committed_ms"]
                    expected += 1
                    if at_ms is None or tx["committed_ms"] <= at_ms:
                        with conn:
                            for event in tx["events"]:
                                apply_event(conn, event)
                        applied = tx["id"]
            if expected != m["end_tx"] + 1 or previous_time != m["covered_ms"]:
                raise BackupError("Incremental incompleto")
        # A restored database starts a NEW journal epoch on server startup.
        for table in ("recovery_events", "recovery_transactions", "recovery_control"):
            conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        conn.commit()
        integrity(conn)
        counts = {name: conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0] for name in COLUMNS}
    return {"database": base["database"], "applied_tx": applied, "target_time": iso(at_ms) if at_ms is not None else "latest", **counts}


def restore(repo, backup_id, destination, at_ms=None):
    destination = Path(destination).resolve()
    if destination.exists():
        raise BackupError("Destino já existe. Restaure em uma pasta NOVA, fora de um servidor em execução")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".nexus-restore-", dir=destination.parent))
    try:
        result = materialize(repo, backup_id, stage / "nexusdb.sqlite", at_ms)
        (stage / "restore-report.json").write_bytes(canonical(result))
        # Existing directories (even empty ones) are never replaced.
        if destination.exists():
            raise BackupError("Destino foi criado durante a restauração")
        stage.rename(destination)
        result["destination"] = str(destination)
        return result
    finally:
        if stage.exists():
            if stage.resolve().parent != destination.parent or not stage.name.startswith(".nexus-restore-"):
                raise BackupError("Diretório temporário inesperado; limpeza cancelada")
            shutil.rmtree(stage)  # verified exact directory returned by mkdtemp


def parser():
    p = argparse.ArgumentParser(description="NexusDB Backup — full, incremental e PITR por banco")
    p.add_argument("--version", action="version", version="nexus-backup 1.0")
    sub = p.add_subparsers(dest="command", required=True)
    for command in ("backup", "archive"):
        a = sub.add_parser(command)
        a.add_argument("--repo", type=Path, required=True)
        a.add_argument("--data-root", type=Path, required=True)
        a.add_argument("--database", required=True)
        a.add_argument("--parent", help="ID do backup anterior (obrigatório para incremental)")
        a.add_argument("--flush-url", help="URL do MESMO nó local; força flush antes da captura")
        a.add_argument("--user", default="admin")
        a.add_argument("--password-env", default="NEXUSDB_PASSWORD")
        a.add_argument("--offline", action="store_true", help="Declara que a origem está parada (full legado)")
        if command == "backup":
            a.add_argument("--type", choices=("full", "incremental"), default="full")
        else:
            a.add_argument("--interval", type=float, default=30)
            a.add_argument("--once", action="store_true")
    for command in ("list", "verify", "restore"):
        a = sub.add_parser(command)
        a.add_argument("--repo", type=Path, required=True)
        if command != "list":
            a.add_argument("--backup", required=True, help="ID do full ou último incremental da cadeia")
        if command == "restore":
            a.add_argument("--destination", type=Path, required=True)
            a.add_argument("--at", help="Instante ISO 8601 com fuso, por exemplo 2026-09-24T15:30:00-03:00")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command in ("backup", "archive"):
        database_name(args.database)
        source = args.data_root / args.database / "nexusdb.sqlite"
        if args.command == "archive" and args.interval <= 0:
            raise BackupError("Intervalo deve ser positivo")
        kind = args.type if args.command == "backup" else "incremental"
        if kind == "incremental" and not args.parent:
            raise BackupError("Informe --parent com o ID anterior")
        while True:
            if args.flush_url:
                flush_source(args.flush_url, args.user, args.password_env, args.database)
            print(f"Capturando {kind}: {args.database}...", file=sys.stderr, flush=True)
            result = backup(args.repo, source, args.database, kind, args.parent, args.offline, bool(args.flush_url))
            print(json.dumps(result, ensure_ascii=False), flush=True)
            if args.command == "backup" or args.once:
                return
            args.parent = result["id"]
            time.sleep(args.interval)
    elif args.command == "list":
        for _, m in sorted(catalog(args.repo).values(), key=lambda item: item[1]["created_ms"]):
            print(json.dumps({k: m[k] for k in ("id", "kind", "database", "parent", "end_tx", "covered_ms")}, ensure_ascii=False))
    elif args.command == "verify":
        with tempfile.TemporaryDirectory(prefix="nexus-verify-") as work:
            result = materialize(args.repo, args.backup, Path(work) / "verify.sqlite")
        print(json.dumps({"verified": True, **result}, ensure_ascii=False))
    else:
        result = restore(args.repo, args.backup, args.destination, utc_ms(args.at) if args.at else None)
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrompido; pacotes publicados anteriormente permanecem válidos.", file=sys.stderr)
        sys.exit(130)
    except (BackupError, OSError, sqlite3.Error, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"ERRO: {error}", file=sys.stderr)
        sys.exit(1)
