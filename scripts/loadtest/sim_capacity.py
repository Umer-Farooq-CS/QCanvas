"""Max execute-qsim throughput: N guests each hammer the endpoint (stays under the 30/min/user limit).
usage: python sim_capacity.py <base> [users=24] [seconds=40]"""
import sys, time, json, threading, urllib.request, urllib.error
base=sys.argv[1]; N=int(sys.argv[2]) if len(sys.argv)>2 else 24; DUR=float(sys.argv[3]) if len(sys.argv)>3 else 40
Q='OPENQASM 3.0;\ninclude "stdgates.inc";\nbit[2] c;\nqubit[2] q;\nh q[0];\ncx q[0], q[1];\nc[0] = measure q[0];\nc[1] = measure q[1];\n'
def post(path, body, tok=None):
    req=urllib.request.Request(base+path, json.dumps(body).encode(), {"Content-Type":"application/json", **({"Authorization":"Bearer "+tok} if tok else {})})
    t=time.time()
    try:
        r=urllib.request.urlopen(req, timeout=120); d=json.loads(r.read()); c=r.status
    except urllib.error.HTTPError as e: d=None; c=e.code
    except Exception: d=None; c=0
    return c,d,time.time()-t
toks=[post("/api/auth/guest",{})[1]["access_token"] for _ in range(N)]
lat=[]; codes={}
end=time.time()+DUR
def w(tok):
    while time.time()<end:
        c,d,dt=post("/api/simulator/execute-qsim",{"qasm_input":Q,"backend":"qiskit","shots":1024},tok)
        codes[c]=codes.get(c,0)+1
        if c==200: lat.append(dt)
        else: time.sleep(1)
ts=[threading.Thread(target=w,args=(t,)) for t in toks]
t0=time.time(); [t.start() for t in ts]; [t.join() for t in ts]; el=time.time()-t0
lat.sort(); n=len(lat)
print(base,"users",N,"ok",n,"codes",codes,"thru %.1f/s"%(n/el),"p50 %.2f p95 %.2f"%(lat[n//2],lat[int(n*.95)]) if n else "")
for t in toks: post("/api/auth/logout",{},t)
