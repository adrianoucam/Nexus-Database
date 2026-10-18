"""REST benchmark with generated representative graphs, isolated servers.

Defaults: 10k vertices, directed ring, 3 samples, concurrency 2. Larger sizes
require explicit --sizes 10000 100000 1000000. This is not a production SLA.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
import os
from pathlib import Path
import platform
import secrets
import socket
import statistics
import subprocess
import time
import urllib.request
import urllib.error
from crypto_temporal_lab import NexusSession, REPO
from nexusdb_ai.gateway_adapter import GatewayTransport

def rss(pid):
    if os.name != 'nt':return None
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[(name,ctypes.c_size_t) for name in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.restype=ctypes.c_void_p;kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x410,False,pid)
    if not handle:return None
    try:
        counters=Counters();counters.cb=ctypes.sizeof(counters);api=ctypes.WinDLL('psapi',use_last_error=True);api.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
        if not api.GetProcessMemoryInfo(handle,ctypes.byref(counters),counters.cb):return None
        return {'working_set_bytes':counters.WorkingSetSize,'process_peak_since_start_bytes':counters.PeakWorkingSetSize}
    finally:kernel.CloseHandle(handle)

def summary(values):
    ordered=sorted(values)
    def pct(p):
        at=(len(ordered)-1)*p;low=int(at);high=min(low+1,len(ordered)-1);return ordered[low]+(ordered[high]-ordered[low])*(at-low)
    return {'count':len(values),'p50_ms':pct(.5),'p95_ms':pct(.95),'p99_ms':pct(.99),'mean_ms':statistics.mean(values)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server',type=Path,default=REPO/'target/debug/nexusdb.exe')
    parser.add_argument('--gateway',type=Path,default=REPO/'crates/nexusdb-rest-gateway/target/debug/nexusdb-rest-gateway.exe')
    parser.add_argument('--sizes',type=int,nargs='+',default=[10000]);parser.add_argument('--samples',type=int,default=3)
    parser.add_argument('--concurrency',type=int,default=2);parser.add_argument('--output',type=Path,default=Path('rest-benchmark-output'))
    parser.add_argument('--enable-gpu',action='store_true',help='Enable CUDA only when server/plugin/hardware support it')
    args=parser.parse_args()
    if any(not 2<=n<=1000000 for n in args.sizes) or not 1<=args.samples<=100 or not 1<=args.concurrency<=16:parser.error('Invalid workload budget')
    root=args.output.resolve()/f'run-{time.time_ns()}';root.mkdir(parents=True)
    report={'hardware':{'os':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),'cuda_enabled_requested':args.enable_gpu,'server_build_profile':args.server.resolve().parent.name,'server':str(args.server.resolve()),'gateway':str(args.gateway.resolve())},'runs':[],'limitations':['Generated directed ring, not real patient/customer data','End-to-end latency includes authentication','Peak working set includes ingestion and all calls since server start','VRAM unavailable unless reported by native CUDA telemetry','p95/p99 with few samples are exploratory, not stable estimates']}
    for size in args.sizes:
        directory=root/str(size);directory.mkdir();db=f'EXAMPLE_REST_BENCH_{size}'
        session=NexusSession(args.server.resolve(strict=True),directory,database=db,environment={'NEXUSDB_CUDA_ENABLED':'true'} if args.enable_gpu else None);process=None;log=None
        try:
            print(f'Loading {size} vertices and edges...',flush=True)
            for first in range(0,size,5000):session.request('/db/data/node/bulk',{'rows':[{'key':str(i),'label':'Vertex','properties':{'index':i}} for i in range(first,min(first+5000,size))]})
            for first in range(0,size,5000):session.request('/db/data/relationship/bulk',{'rows':[{'key':str(i),'from':i+1,'to':(i+1)%size+1,'type':'LINK','properties':{}} for i in range(first,min(first+5000,size))]})
            endpoints={backend:{'database':db,'user_env':'BENCH_USER','password_env':'BENCH_PASSWORD','backend':backend,'max_rows':1,'operation':{'kind':'call','procedure':'graph.projectPageRank','args':{'iterations':20},'columns':{'node_id':'/node_id','rank':'/page_rank'}}} for backend in ('CPU_SERIAL','CPU_PARALLEL','AUTO','CUDA')}
            config=directory/'endpoints.json';config.write_text(json.dumps({'endpoints':endpoints,'database_limits':{db:{'max_inflight':args.concurrency,'timeout_ms':30000,'managed_memory_mb':256}}}),encoding='utf8')
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            admin=secrets.token_urlsafe(32);url=f'http://127.0.0.1:{port}'
            env=os.environ|{'NEXUSDB_GATEWAY_CONFIG':str(config),'NEXUSDB_GATEWAY_STATE':str(directory/'control.sqlite'),'NEXUSDB_GATEWAY_BIND':f'127.0.0.1:{port}','NEXUSDB_GATEWAY_ADMIN_KEY':admin,'NEXUSDB_BASE_URL':session.url,'BENCH_USER':'admin','BENCH_PASSWORD':session.password}
            log=(directory/'gateway.log').open('w',encoding='utf8');process=subprocess.Popen([str(args.gateway.resolve(strict=True))],cwd=directory,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            for _ in range(200):
                if process.poll() is not None:raise RuntimeError('Gateway failed; see log')
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):break
                except OSError:time.sleep(.05)
            else:raise TimeoutError('Gateway readiness')
            keys={}
            for endpoint in endpoints:
                req=urllib.request.Request(url+'/admin/endpoints/'+endpoint+'/keys',json.dumps({'ttl_seconds':3600}).encode(),headers={'Content-Type':'application/json','X-Gateway-Admin-Key':admin})
                with urllib.request.urlopen(req) as response:keys[endpoint]=json.load(response)['api_key']
            transport=GatewayTransport(url,keys)
            for backend in endpoints:
                def sample():
                    started=time.perf_counter();response=transport.call(backend)
                    if abs(response['rows'][0]['rank']-1/size)>1e-10:raise AssertionError('PageRank ring reference mismatch')
                    return {'elapsed_ms':(time.perf_counter()-started)*1000,'execution':response['meta']['native']['execution'],'rss':rss(session.process.pid)}
                run={'vertices':size,'edges':size,'backend_requested':backend,'iterations':20,'samples':[],'gateway_rss':rss(process.pid)}
                try:
                    first=sample();run['first_request']=first
                    for concurrency in sorted({1,args.concurrency}):
                        with ThreadPoolExecutor(max_workers=concurrency) as pool:
                            started=time.perf_counter();values=list(pool.map(lambda _:sample(),range(args.samples)));elapsed=time.perf_counter()-started
                        if any(v['execution']['nodes']!=size for v in values):raise AssertionError('Graph size mismatch')
                        selected={v['execution']['selected_backend'] for v in values}
                        if backend=='CUDA' and selected!={'CUDA'}:raise AssertionError('CUDA not selected')
                        run['samples'].append({'concurrency':concurrency,'throughput_requests_s':len(values)/elapsed,'end_to_end':summary([v['elapsed_ms'] for v in values]),'native_compute':summary([v['execution']['compute_ms'] for v in values]),'selected_backends':sorted(selected),'observations':values})
                    run['status']='measured'
                except RuntimeError as error:
                    if backend!='CUDA':raise
                    run['status']='unavailable';run['reason']='CUDA request rejected; no GPU result measured. Enable CUDA and use a compatible server/plugin/hardware to measure.'
                report['runs'].append(run);(root/'benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(size,backend,run['status'],flush=True)
        finally:
            if process is not None and process.poll() is None:process.terminate();process.wait(timeout=15)
            if log:log.close()
            session.close()
    print('Report:',root/'benchmark.json')

if __name__=='__main__':main()
