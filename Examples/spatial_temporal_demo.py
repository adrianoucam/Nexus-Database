"""Demonstração isolada: Python padrão/Tkinter + funções nativas NexusDB."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from crypto_temporal_lab import NexusSession, REPO

DB = 'EXAMPLE_SPATIAL_TEMPORAL'
CENTER = (-46.6333, -23.5505)


def dataset():
    locations = [('Hospital A', 0, 0, 0, None), ('Hospital B', .012, .008, 0, None),
                 ('Hospital C', .023, -.003, 0, 10), ('Hospital D', .035, .012, 10, None),
                 ('Posto E', -.015, .004, 0, None), ('Posto F', .06, .025, 0, None)]
    return {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'id': name, 'geometry': {'type': 'Point', 'coordinates': [CENTER[0]+dx, CENTER[1]+dy]},
         'properties': {'name': name, 'valid_from': start, 'valid_to': end}}
        for name, dx, dy, start, end in locations]}


def query(session, text, parameters=None):
    value = session.request('/db/data/cypher', {'statements': [{'query': text, 'parameters': parameters or {}}]})
    return value['resultados'][0]


def prepare(session, output):
    checks = []
    def check(name, condition):
        if not condition: raise AssertionError(name)
        checks.append(name)
    features = dataset()
    imported = session.call('spatial.importGeoJSON', {'collection': features, 'label': 'Hospital'})
    ids = [row['node_id'] for row in imported['resultados']]
    check('GeoJSON: seis pontos importados atomicamente', imported['processados'] == 6)
    rows = [{'key': f'link-{a}-{b}', 'from': ids[a], 'to': ids[b], 'type': 'TRANSFER',
             'properties': {'layer': 'care', 'valid_from': 0}} for a, b in [(0, 1), (1, 2), (1, 3), (0, 4), (4, 5), (5, 3)]]
    session.request('/db/data/relationship/bulk', {'rows': rows})
    original = session.call('graph.historyStatus', {})['stamp']['recorded_at']
    session.call('graph.historyCheckpoint', {})
    radius = {'kind': 'radius', 'longitude': CENTER[0], 'latitude': CENTER[1], 'radius_m': 3000}
    near = session.call('spatial.search', {'projection': {'spatial': radius}})
    check('Raio em metros, resultado ordenado', near['processados'] == 4 and near['resultados'][0]['node_id'] == ids[0])
    before = session.call('spatial.search', {'projection': {'node_temporal': {'kind': 'at', 'timestamp': 5}}})
    after = session.call('spatial.search', {'projection': {'node_temporal': {'kind': 'at', 'timestamp': 15}}})
    check('Intervalo [início,fim): C sai e D entra', ids[2] in [r['node_id'] for r in before['resultados']] and ids[2] not in [r['node_id'] for r in after['resultados']] and ids[3] in [r['node_id'] for r in after['resultados']])
    exported = session.call('spatial.exportGeoJSON', {})['collection']
    check('GeoJSON preserva nomes e identificadores de origem', exported['features'][0]['id'] == 'Hospital A' and exported['features'][0]['properties']['name'] == 'Hospital A')
    polygon = {'type': 'Polygon', 'coordinates': [[[CENTER[0]-.025, CENTER[1]-.015], [CENTER[0]+.045, CENTER[1]-.015],
                [CENTER[0]+.045, CENTER[1]+.02], [CENTER[0]-.025, CENTER[1]+.02], [CENTER[0]-.025, CENTER[1]-.015]]]}
    inside = session.call('spatial.search', {'projection': {'spatial': {'kind': 'within', 'geometry': polygon}}})
    check('Predicado dentro do polígono', inside['processados'] == 5)
    path = session.call('spatial.shortestPath', {'start': ids[0], 'end': ids[3], 'directed': True,
            'projection': {'node_temporal': {'kind': 'at', 'timestamp': 15}, 'layers': ['care']}})
    check('Dijkstra nativo com pesos Haversine', path['found'] and path['resultados'][0]['path'] == [ids[0], ids[1], ids[3]] and path['resultados'][0]['distance_m'] > 0)
    scalar = query(session, 'RETURN spatial.distance($a,$b) AS meters', {'a': {'longitude': 179.9, 'latitude': 0}, 'b': {'longitude': -179.9, 'latitude': 0}})
    check('Distância atravessa antimeridiano', 22000 < scalar['meters'] < 23000)
    query(session, f'MATCH (n:Hospital) WHERE id(n)={ids[1]} SET n.geometry=$geometry RETURN n',
          {'geometry': {'type': 'Point', 'coordinates': [CENTER[0]+.08, CENTER[1]+.04], 'srid': 4326}})
    current = session.call('spatial.search', {'projection': {'spatial': radius}})
    history = session.call('spatial.search', {'projection': {'spatial': radius, 'system_at': original}})
    check('Correção de localização invalida índice/cache', current['processados'] == 3)
    check('Checkpoint e histórico mantêm posição anterior', history['processados'] == 4)
    project = session.call('graph.project', {'projection': {'spatial': radius, 'system_at': original, 'layers': ['care']}})
    check('Filtro espacial compõe CSR e camada', project['total_nodes'] == 4 and project['total_relationships'] == 3)
    report = {'database': DB, 'checks': checks, 'verified': len(checks), 'history_stamp': original,
              'distance_model': 'haversine_sphere', 'units': 'm', 'original_geojson': exported,
              'path': path, 'trace': session.trace}
    (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    (output/'places.geojson').write_text(json.dumps(exported, ensure_ascii=False, indent=2), encoding='utf8')
    for index, name in enumerate(checks, 1): print(f'{index}. {name}')
    return {'ids': ids, 'stamp': original, 'polygon': polygon, 'edges': rows}


def display(session, state, smoke=False):
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk(); root.title('NexusDB — laboratório espacial e temporal'); root.geometry('1120x760')
    ttk.Label(root, text='Localizações simuladas de atendimento — longitude/latitude WGS84', font=('Segoe UI', 15, 'bold')).pack(pady=10)
    ttk.Label(root, text='Distâncias em metros por Haversine. O desenho é um plano de coordenadas; os caminhos seguem relações simuladas.').pack()
    controls = ttk.Frame(root); controls.pack(fill='x', padx=15, pady=12)
    radius = tk.DoubleVar(value=3000); instant = tk.IntVar(value=5); historical = tk.BooleanVar(value=True)
    mode = tk.StringVar(value='Raio'); status = tk.StringVar(value='Consultando NexusDB...')
    ttk.Label(controls, text='Raio (m)').pack(side='left'); ttk.Entry(controls, textvariable=radius, width=8).pack(side='left', padx=8)
    ttk.Label(controls, text='Instante de validade').pack(side='left'); ttk.Scale(controls, from_=0, to=20, variable=instant, length=200).pack(side='left', padx=8)
    ttk.Checkbutton(controls, text='Posição original (histórico)', variable=historical).pack(side='left', padx=8)
    ttk.Combobox(controls, textvariable=mode, values=['Raio', 'Área', 'Todos'], state='readonly', width=9).pack(side='left')
    body = ttk.Frame(root); body.pack(fill='both', expand=True, padx=15)
    canvas = tk.Canvas(body, background='#f1f5f9', width=720, height=520, highlightthickness=0); canvas.pack(side='left', fill='both', expand=True)
    details = tk.Text(body, width=38, wrap='word'); details.pack(side='right', fill='y', padx=(12, 0))
    ttk.Label(root, textvariable=status).pack(pady=10)
    executor = ThreadPoolExecutor(max_workers=1); pending = [None]; selected = [None]; latest = [{}]
    def xy(lon, lat):
        return ((lon-(CENTER[0]-.03))/.13*(canvas.winfo_width()-60)+30, 30+(CENTER[1]+.06-lat)/.085*(canvas.winfo_height()-60))
    def paint(value):
        latest[0] = value; canvas.delete('all'); rows = value['rows']; positions = {r['node_id']: xy(*r['geometry']['coordinates']) for r in rows}
        if value['mode'] == 'Área':
            coords = [v for pair in state['polygon']['coordinates'][0] for v in xy(*pair)]
            canvas.create_polygon(*coords, fill='#e0f2fe', outline='#0284c7', width=2)
        path = value.get('path', []); route_pairs = set(zip(path, path[1:]))
        for edge in state['edges']:
            if edge['from'] in positions and edge['to'] in positions:
                canvas.create_line(*positions[edge['from']], *positions[edge['to']], fill='#dc2626' if (edge['from'], edge['to']) in route_pairs else '#94a3b8', width=4 if (edge['from'], edge['to']) in route_pairs else 1, arrow='last')
        for row in rows:
            x, y = positions[row['node_id']]
            marker = canvas.create_oval(x-8, y-8, x+8, y+8, fill='#0f766e', outline='white', width=2)
            canvas.create_text(x, y-19, text=row['properties']['name'], font=('Segoe UI', 10))
            canvas.tag_bind(marker, '<Button-1>', lambda event, row=row: show(row))
        status.set(f"{len(rows)} pontos | validade t={value['time']} | {'histórico original' if value['historical'] else 'posição corrigida'} | clique nos pontos | caminho A→D: {value.get('distance', 'indisponível')}")
        if selected[0] in {r['node_id'] for r in rows}: show(next(r for r in rows if r['node_id'] == selected[0]))
        else: details.delete('1.0', 'end'); details.insert('end', 'Clique em um ponto para ver dados devolvidos pelo NexusDB.\n\nC é válido antes de t=10. D é válido a partir de t=10.\n\nDesmarque histórico para ver a correção da posição de B. A linha vermelha mostra o caminho mínimo por distância entre A e D, quando existente.\n\nEssas relações não são uma malha viária e a distância não representa tempo de viagem.')
    def show(row):
        selected[0] = row['node_id']; details.delete('1.0', 'end'); details.insert('end', json.dumps(row, ensure_ascii=False, indent=2))
    def update():
        if pending[0] is not None: return
        try:
            meters = float(radius.get()); t = int(instant.get()); original = historical.get(); choice = mode.get()
            if not 0 <= meters <= 50000: raise ValueError('Raio entre 0 e 50000 m')
        except (ValueError, tk.TclError) as error: status.set(str(error)); return
        def fetch():
            spec = {'node_temporal': {'kind': 'at', 'timestamp': t}}
            if original: spec['system_at'] = state['stamp']
            if choice == 'Raio': spec['spatial'] = {'kind': 'radius', 'longitude': CENTER[0], 'latitude': CENTER[1], 'radius_m': meters}
            elif choice == 'Área': spec['spatial'] = {'kind': 'within', 'geometry': state['polygon']}
            result = session.call('spatial.search', {'projection': spec})
            value = {'rows': result['resultados'], 'mode': choice, 'time': t, 'historical': original}
            if {state['ids'][0], state['ids'][3]} <= {r['node_id'] for r in value['rows']}:
                path = session.call('spatial.shortestPath', {'start': state['ids'][0], 'end': state['ids'][3], 'directed': True, 'projection': spec | {'layers': ['care']}})
                if path['found']: value.update(path=path['resultados'][0]['path'], distance=f"{path['resultados'][0]['distance_m']:.1f} m")
            return value
        pending[0] = executor.submit(fetch); status.set('Consultando APIs nativas...')
    def poll():
        if pending[0] is not None and pending[0].done():
            try: paint(pending[0].result())
            except Exception as error: status.set(str(error))
            pending[0] = None
        root.after(100, poll)
    ttk.Button(controls, text='Consultar', command=update).pack(side='left', padx=8)
    canvas.bind('<Configure>', lambda event: paint(latest[0]) if latest[0] else None)
    smoke_state = {'phase': 0, 'failure': None}
    def smoke_step():
        if latest[0] and pending[0] is None:
            if not canvas.find_all(): smoke_state['failure'] = 'Canvas sem geometrias'; close(); return
            if smoke_state['phase'] == 0:
                smoke_state['phase'] = 1; mode.set('Todos'); instant.set(12); historical.set(False); update()
            else:
                if not latest[0].get('path'): smoke_state['failure'] = 'Caminho não desenhado'
                else: show(latest[0]['rows'][0]); print('Tk smoke: pontos, relações, histórico, caminho e detalhes verificados')
                close(); return
        root.after(150, smoke_step)
    def smoke_timeout(): smoke_state['failure'] = 'Tk smoke timeout'; close()
    if smoke: root.after(500, smoke_step); root.after(30000, smoke_timeout)
    def close(): executor.shutdown(wait=True, cancel_futures=True); root.destroy()
    root.protocol('WM_DELETE_WINDOW', close); root.after(100, poll); root.after(200, update); root.mainloop()
    if smoke_state['failure']: raise AssertionError(smoke_state['failure'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=REPO/'target'/'debug'/'nexusdb.exe')
    parser.add_argument('--output', type=Path, default=Path('spatial-python-output'))
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--smoke-gui', action='store_true', help='Valida o canvas e encerra automaticamente')
    args = parser.parse_args(); binary = args.server.resolve(strict=True)
    output = args.output.resolve()/f'run-{time.time_ns()}'; output.mkdir(parents=True)
    session = NexusSession(binary, output, database=DB)
    try:
        state = prepare(session, output)
        print('Relatório:', output/'report.json')
        if not args.headless: display(session, state, smoke=args.smoke_gui)
    finally: session.close()


if __name__ == '__main__': main()
