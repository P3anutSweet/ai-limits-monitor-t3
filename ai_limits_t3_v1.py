"""AI Limits Monitor, T3 edition: a small page for T3 Code's right-panel Preview tab.

Serves http://localhost:<port>/ (default 47823) on this PC only. Open the Preview tab in T3 Code's right panel and
enter localhost:47823. The page shows your AI subscription usage (Claude, Codex, Gemini, DeepSeek and more) and
refreshes itself.

Data: with source = "auto" (default) the page uses the desktop edition's latest.json while it is fresh (no second
request to the vendors), otherwise it reads usage itself with the same readers as the desktop edition
(ai_limits_core_v1.py). Login tokens are only read, never written, logged, printed or served.

Run:  python ai_limits_t3_v1.py              serve (Ctrl+C stops)
      pythonw ai_limits_t3_v1.py             serve without a console window
      python ai_limits_t3_v1.py --demo       sample data only (screenshots, trying the look)
      python ai_limits_t3_v1.py --once       print the data the page would show, then exit
"""
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ai_limits_core_v1 as core  # noqa: E402

S = core.S
PORT = S["port"]
AVATAR_RE = re.compile(r"^/avatars/([a-z_]+_512\.png)$")
_DATA = {"services": [], "checked_at": None, "source": "starting", "note": ""}
_LOCK = threading.Lock()


# ---------- data ----------
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024


def _num(v):
    import math
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    v = float(v)
    return v if math.isfinite(v) else None


def _txt(v, limit=300):
    return v[:limit] if isinstance(v, str) else None


def _pairs(rows):
    out = []
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, str):
            r = ["info", r]
        if isinstance(r, (list, tuple)) and len(r) == 2 and isinstance(r[0], str) and isinstance(r[1], str):
            out.append([r[0][:20], r[1][:300]])
    return out


def clean_service(s):
    """Only the fields the page shows, with checked types; anything malformed is dropped (never passed on)."""
    if not isinstance(s, dict) or not isinstance(s.get("name"), str):
        return None
    out = {"name": s["name"][:40], "error": _txt(s.get("error")), "stale": s.get("stale") is True,
           "badge": _txt(s.get("badge"), 40), "notes": _pairs(s.get("notes")), "meters": []}
    if isinstance(s.get("signed_in"), bool):
        out["signed_in"] = s["signed_in"]
        out["status_lines"] = _pairs(s.get("status_lines"))
    for m in s.get("meters") if isinstance(s.get("meters"), list) else []:
        if not isinstance(m, dict) or _num(m.get("pct")) is None or not isinstance(m.get("label"), str):
            continue
        out["meters"].append({"key": _txt(m.get("key"), 120) or "", "label": m["label"][:80],
                              "pct": max(0.0, min(_num(m["pct"]), 1000.0)), "resets_at": _num(m.get("resets_at")),
                              "window": _num(m.get("window")), "detail": _txt(m.get("detail"), 120) or ""})
    return out


def from_latest_json():
    """Services from the desktop edition's latest.json, or None when missing, too big, malformed or not fresh."""
    try:
        with open(S["latest_json"], "rb") as f:
            raw = f.read(MAX_SNAPSHOT_BYTES + 1)
        if len(raw) > MAX_SNAPSHOT_BYTES:
            return None
        snap = json.loads(raw.decode("utf-8"))
        import datetime as dt
        if not isinstance(snap, dict) or not isinstance(snap.get("services"), list):
            return None
        age = time.time() - dt.datetime.fromisoformat(str(snap["checked_at"])).timestamp()
        if not (-60 <= age <= float(S["max_age_minutes"]) * 60):     # small clock skew allowed, no future snapshots
            return None
        by_name = {}
        for s in snap["services"]:
            c = clean_service(s)
            if c:
                by_name[c["name"]] = c
        return [by_name[n] for n in S["services"] if n in by_name], snap["checked_at"]
    except Exception:
        return None


def read_self():
    out = []
    for f in core.ALL_FETCHERS:
        try:
            out.append(f())
        except Exception as e:   # one vendor failing never stops the page
            out.append({"name": {"big_fat_fish": "DeepSeek", "glm": "GLM", "minimax": "MiniMax"}.get(f.__name__[6:], f.__name__[6:].title()), "plan": "", "meters": [], "notes": [],
                        "error": type(e).__name__})
    return out


def refresh():
    src = str(S["source"]).lower()
    got = None if (core.DEMO or src == "self") else from_latest_json()
    if core.DEMO:
        services, source, checked = read_self(), "sample data", time.time()
    elif got is not None:
        services, checked = got
        source = "desktop monitor"
    elif src == "file":
        services, source, checked = [], "waiting for the desktop monitor's latest.json", None
    else:
        services, source, checked = read_self(), "read directly", time.time()
    services = [c for c in (clean_service(s) for s in services) if c]
    with _LOCK:
        old = {s["name"]: s for s in _DATA["services"]}
        for s in services:   # keep the last values when a vendor briefly fails
            if s.get("error") and not s.get("meters") and old.get(s["name"], {}).get("meters"):
                s["meters"], s["stale"] = old[s["name"]]["meters"], True
        _DATA.update(services=services, source=source, checked_at=checked)


def refresher():
    while True:
        try:
            refresh()
        except Exception as e:
            sys.stderr.write(f"refresh failed: {type(e).__name__}\n")
        time.sleep(max(30.0, float(S["refresh_minutes"]) * 60))


def payload():
    with _LOCK:
        services = json.loads(json.dumps(_DATA["services"]))   # a copy
        checked, source = _DATA["checked_at"], _DATA["source"]
    for s in services:
        s["display_name"] = core.DISPLAY_NAME.get(s["name"], s["name"])
        av = core.AVATAR_KEY.get(s["name"], "") + "_512.png"
        s["avatar"] = av if AVATAR_RE.match("/avatars/" + av) and os.path.isfile(os.path.join(S["avatar_dir"], av)) else None
    tz = core.TZ.utcoffset(None).total_seconds() / 60 if core.TZ else None
    return {"services": services, "checked_at": checked, "source": source, "demo": core.DEMO,
            "tz_offset_minutes": tz, "tz_label": S["time_zone_label"], "now": time.time()}


# ---------- server ----------
class ExclusiveServer(ThreadingHTTPServer):
    """No address reuse: on Windows the port is reserved exclusively, so a second copy cannot bind it too."""
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        import socket
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    server_version = "ai-limits-t3"
    sys_version = ""

    def log_message(self, *a):   # quiet: no request log
        pass

    def _host_ok(self):
        """Only requests addressed to this PC's loopback name (stops DNS-rebinding pages from reading the data)."""
        host = (self.headers.get("Host") or "").lower()
        return host in (f"localhost:{PORT}", f"127.0.0.1:{PORT}", f"[::1]:{PORT}")

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; "
                         "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; "
                         "frame-ancestors *")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, b"forbidden", "text/plain; charset=utf-8")
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        if path == "/api/usage":
            return self._send(200, json.dumps(payload(), ensure_ascii=False).encode("utf-8"),
                              "application/json; charset=utf-8")
        m = AVATAR_RE.match(path)
        if m:
            p = os.path.join(S["avatar_dir"], m.group(1))
            if os.path.isfile(p):
                with open(p, "rb") as f:
                    return self._send(200, f.read(), "image/png")
        return self._send(404, b"not found", "text/plain; charset=utf-8")


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Limits</title>
<style>
:root{--bg1:#5c6678;--bg2:#3a4252;--card:rgba(255,255,255,.07);--line:rgba(255,255,255,.12);--txt:#eceff4;--sub:#bac4d0;
--faint:#96a1b0;--track:rgba(255,255,255,.13);--teal:#8ac4ba;--purple:#b09ed8;--rose:#d696a2;--ok:#98bca2;--high:#d69898;
--blue:#7ca8de;--tick:rgba(255,255,255,.85)}
@media (prefers-color-scheme: light){:root{--bg1:#e9edf3;--bg2:#d4dae4;--card:rgba(255,255,255,.62);--line:rgba(40,50,70,.12);
--txt:#1f2633;--sub:#3e4859;--faint:#6a7586;--track:rgba(40,50,70,.12);--tick:#5b6474}}
*{box-sizing:border-box}html,body{margin:0;overflow-x:hidden}
body{min-height:100vh;background:linear-gradient(180deg,var(--bg1),var(--bg2));color:var(--txt);
font:14px/1.35 "Comic Sans MS","Segoe UI","Microsoft YaHei UI",sans-serif;padding:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:12px 14px;margin:0 0 10px;
display:grid;grid-template-columns:52px minmax(0,1fr);gap:4px 12px;width:100%;backdrop-filter:blur(8px);position:relative;overflow:hidden}
.card:before{content:"";position:absolute;left:0;top:14px;bottom:14px;width:3px;border-radius:2px;background:var(--acc,#888)}
.av{width:52px;height:52px;border-radius:50%;object-fit:cover;border:1.5px solid rgba(255,255,255,.55);background:#fff}
.head{display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-height:22px}
.name{font-weight:700;font-size:15px;min-width:0;overflow-wrap:anywhere}.badge{font-size:11px;font-weight:700;padding:1px 8px;border-radius:9px;background:rgba(128,140,165,.28)}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}.st{font-weight:700;font-size:12.5px}
.meter{margin:6px 0 2px}.mrow{display:flex;justify-content:space-between;gap:8px;font-size:13px}.mrow span:first-child{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pct{font-weight:700}.bar{position:relative;height:5px;border-radius:3px;background:var(--track);margin:4px 0 2px}
.fill{position:absolute;left:0;top:0;bottom:0;border-radius:3px}.tick{position:absolute;top:-3px;width:2px;height:11px;
background:var(--tick);border-radius:1px}.small{font-size:11.5px;color:var(--faint);overflow-wrap:anywhere}
.note{font-size:12px;color:var(--sub);display:flex;gap:6px;align-items:center;margin-top:3px;min-width:0;overflow-wrap:anywhere}.avx{width:52px;height:52px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:20px;color:#fff;background:var(--acc,#888)}
.free{color:var(--ok);font-weight:700}.err{color:#d8c08e;font-size:12px;margin-top:3px;overflow-wrap:anywhere}
.body{min-width:0}.foot{font-size:11px;color:var(--faint);text-align:center;margin:6px 0 2px}
.empty{color:var(--sub);text-align:center;padding:30px 10px}
</style></head><body>
<div id="list"><div class="empty">Loading…</div></div>
<div class="foot" id="foot"></div>
<script>
"use strict";
const ACC={Claude:"#d09882",Codex:"#8eaecc",Grok:"#b696aa",Gemini:"#96a8d6",DeepSeek:"#80a0c8",Kimi:"#babad4",
Qwen:"#a096ce",Doubao:"#c8aa8c",GLM:"#9698a6",MiniMax:"#d68c96"};
let DATA=null;
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function color(m){const k=m.key||"";if(k.startsWith("codex"))return "var(--purple)";if(k.includes("weekly"))return "var(--purple)";
if(k.includes("session"))return "var(--teal)";if(k.endsWith(":extra"))return "var(--rose)";return "var(--ok)";}
function clock(ts){const off=DATA.tz_offset_minutes;let d;if(off===null){d=new Date(ts*1000);}else{d=new Date((ts+off*60)*1000);}
const g=off===null?{h:d.getHours(),m:d.getMinutes(),w:d.getDay()}:{h:d.getUTCHours(),m:d.getUTCMinutes(),w:d.getUTCDay()};
const now=off===null?new Date():new Date(Date.now()+off*60000);const same=off===null?(now.toDateString()===d.toDateString()):
(now.getUTCFullYear()===d.getUTCFullYear()&&now.getUTCMonth()===d.getUTCMonth()&&now.getUTCDate()===d.getUTCDate());
const hm=String(g.h).padStart(2,"0")+":"+String(g.m).padStart(2,"0");
return (same?"":["Sun","Mon","Tue","Wed","Thu","Fri","Sat"][g.w]+" ")+hm+(DATA.tz_label?" "+DATA.tz_label:"");}
function left(ts){let s=Math.floor(ts-Date.now()/1000);if(s<=0)return "resetting";const d=Math.floor(s/86400);s%=86400;
const h=Math.floor(s/3600),m=Math.floor((s%3600)/60);return d?d+"d "+h+"h":(h?h+"h "+String(m).padStart(2,"0")+"m":m+"m");}
const BOWL='<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><ellipse cx="8" cy="7" rx="5" ry="3" fill="#f6f6f2" stroke="#9aa3b2" stroke-width=".6"/>'+
'<path d="M2 8h12a6 5 0 0 1-12 0z" fill="currentColor"/></svg>';
function meter(m){const pct=Math.max(0,Math.min(100,+m.pct||0));let tick="";
if(m.window&&m.resets_at){const f=(Date.now()/1000-(m.resets_at-m.window))/m.window;if(f>0&&f<1)tick='<span class="tick" style="left:'+(f*100).toFixed(1)+'%"></span>';}
let sub=m.detail?esc(m.detail):"";if(m.resets_at)sub+=(sub?" · ":"")+"resets "+esc(clock(m.resets_at))+" · in "+left(m.resets_at);
const c=pct>=90?"var(--high)":color(m);
return '<div class="meter"><div class="mrow"><span title="'+esc(m.label)+'">'+esc(m.label)+'</span><span class="pct" style="color:'+c+'">'+Math.round(pct)+
'%</span></div><div class="bar"><span class="fill" style="width:'+pct+'%;background:'+color(m)+'"></span>'+tick+'</div>'+
(sub?'<div class="small">'+sub+'</div>':"")+'</div>';}
function note(n){const k=n[0],t=esc(n[1]);if(k==="ok"||k==="bad")return '<div class="note"><span class="dot" style="background:'+
(k==="ok"?"var(--blue)":"var(--high)")+'"></span>'+t+'</div>';if(k.startsWith("rice"))return '<div class="note" style="color:'+
(k==="rice_bad"?"var(--high)":"var(--ok)")+'">'+BOWL+'<span style="color:var(--sub)">'+t+'</span></div>';
return '<div class="note" style="color:var(--faint)">'+t+'</div>';}
function card(s){const acc=ACC[s.name]||"#888";let h='<div class="card" style="--acc:'+acc+'">'+(s.avatar?'<img class="av" alt="" src="/avatars/'+
esc(s.avatar)+'">':'<div class="avx">'+esc((s.display_name||"?").charAt(0))+'</div>')+'<div class="body"><div class="head"><span class="name">'+esc(s.display_name)+'</span>';
if(s.badge)h+='<span class="badge">'+esc(s.badge)+'</span>';
if("signed_in" in s){const c=s.signed_in?"var(--blue)":"var(--high)";h+='<span class="dot" style="background:'+c+'"></span><span class="st" style="color:'+
c+'">'+(s.signed_in?"signed in":"not signed in")+'</span></div>';
for(const l of s.status_lines||[])h+=l[0]==="free"?'<div class="note free">FREE '+esc(l[1])+'</div>':'<div class="note" style="color:var(--faint)">'+esc(l[1])+'</div>';
return h+'</div></div>';}
h+='</div>';if(s.error)h+='<div class="err">'+(s.stale?"last values · ":"")+esc(s.error)+'</div>';
for(const m of s.meters||[])h+=meter(m);for(const n of s.notes||[])h+=note(n);return h+'</div></div>';}
function render(){if(!DATA)return;const L=document.getElementById("list");
L.innerHTML=DATA.services.length?DATA.services.map(card).join(""):'<div class="empty">'+esc(DATA.source)+'</div>';
let f=(DATA.demo&&DATA.source!=="sample data")?"sample data · ":"";if(DATA.checked_at){const t=typeof DATA.checked_at==="number"?DATA.checked_at:Date.parse(DATA.checked_at)/1000;
f+="checked "+esc(clock(t))+" · ";}f+=esc(DATA.source)+" · tick = even pace";document.getElementById("foot").innerHTML=f;}
async function load(){try{const r=await fetch("/api/usage",{cache:"no-store"});const d=await r.json();
if(!d||!Array.isArray(d.services))throw new Error("unexpected data");DATA=d;render();}
catch(e){document.getElementById("foot").textContent="could not load the usage data ("+((e&&e.message)||e)+"); retrying";}}
load();setInterval(load,30000);setInterval(render,20000);
</script></body></html>
"""


def main():
    if "--once" in sys.argv:
        refresh()
        print(json.dumps(payload(), ensure_ascii=False, indent=1))
        return 0
    try:
        srv = ExclusiveServer(("127.0.0.1", PORT), Handler)
    except OSError as e:
        sys.stderr.write(f"port {PORT} is in use ({e}); is the page already running? Change 'port' in the settings.\n")
        return 1
    threading.Thread(target=refresher, daemon=True).start()
    print(f"AI Limits (T3 edition) at http://localhost:{PORT}/  - open it in T3 Code's Preview tab. Ctrl+C stops.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
