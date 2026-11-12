"""Per-process CPU sampler for inside the container: python proc_sampler.py <out.csv> <seconds> [interval]"""
import os, sys, time
out, total = sys.argv[1], float(sys.argv[2]); iv = float(sys.argv[3]) if len(sys.argv) > 3 else 15
tck = os.sysconf("SC_CLK_TCK")
def snap():
    d = {}
    for p in os.listdir("/proc"):
        if not p.isdigit(): continue
        try:
            st = open(f"/proc/{p}/stat").read()
            f = st[st.rindex(")") + 2:].split()
            cpu = (int(f[11]) + int(f[12])) / tck
            cmd = open(f"/proc/{p}/cmdline").read().replace("\0", " ")[:70]
            rss = int(f[21]) * 4096 / 1048576
            d[p] = (cpu, cmd, rss)
        except Exception:
            pass
    return d
end = time.time() + total
prev = snap(); t0 = time.time()
with open(out, "w") as fh:
    fh.write("t,pid,cpu_pct,rss_mb,cmd\n")
    while time.time() < end:
        time.sleep(iv)
        cur = snap(); now = time.time()
        for p, (c, cmd, rss) in cur.items():
            if p in prev:
                pct = (c - prev[p][0]) / (now - t0) * 100
                if pct >= 5:
                    fh.write(f"{int(now)},{p},{pct:.0f},{rss:.0f},{cmd.replace(',', ' ')}\n")
        fh.flush(); prev = cur; t0 = now
