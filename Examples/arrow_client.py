"""Authenticated Arrow streaming client. No server file-system access is needed."""
import json
import urllib.request
import pyarrow.ipc as ipc

def export_properties(url, database, user, password, request, timeout=300):
    """Creating an export requires database write access; request is a structured map."""
    body = {'statements': [{'query': 'CALL graph.exportArrow($request)',
                            'parameters': {'request': request}}]}
    req = urllib.request.Request(url.rstrip('/') + '/db/data/cypher',
        data=json.dumps(body).encode(), headers={'Content-Type': 'application/json',
        'X-Database': database, 'X-User': user, 'X-Pass': password})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        result = json.load(response)
    if result.get('errors') or result.get('status') in ('error', 'partial_error'):
        raise RuntimeError(result.get('errors', result.get('error')))
    return result['resultados'][0]

def batches(url, database, user, password, export_id, timeout=300):
    """Yields RecordBatches while holding only the current batch. Requires read access."""
    req = urllib.request.Request(url.rstrip('/') + '/db/data/arrow/download',
        data=json.dumps({'export_id': export_id}).encode(), headers={
        'Content-Type': 'application/json', 'X-Database': database,
        'X-User': user, 'X-Pass': password})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        reader = ipc.open_stream(response)
        yield from reader
