#!/usr/bin/env python3
# perch GUI - a local web dashboard + spatial desktop arranger for the perch CLI.
# Served on 127.0.0.1 only; shells out to perch + yabai. No third-party deps.
import http.server, socketserver, json, os, subprocess, socket
from collections import defaultdict

HOME = os.path.expanduser("~")
CONF = os.environ.get("PERCH_CONFIG",    HOME + "/.config/perch/projects.conf")
FAV  = os.environ.get("PERCH_FAVORITES", HOME + "/.config/perch/favorites")
SETT = os.environ.get("PERCH_SETTINGS",  HOME + "/.config/perch/settings")
SPACES = os.environ.get("PERCH_SPACES",  HOME + "/.config/perch/spaces.conf")
PERCH = os.environ.get("PERCH_BIN", "perch")
PORT = int(os.environ.get("PERCH_GUI_PORT", "7620"))

CAT_ORDER = ["metro", "landing", "web", "backend", "admin", "other"]
CAT_LABEL = {"metro":"Metro","landing":"Landing","web":"Web app",
             "backend":"Backend","admin":"Admin","other":"Other"}

def read_projects():
    out = []
    try:
        for line in open(CONF):
            line = line.strip()
            if not line or line.startswith("#"): continue
            p = line.split("|")
            if len(p) >= 4:
                out.append({"name": p[0], "port": p[1], "dir": p[2], "cmd": p[3]})
    except FileNotFoundError: pass
    return out

def read_favorites():
    try: return [l.strip() for l in open(FAV) if l.strip()]
    except FileNotFoundError: return []

def get_setting(key, default):
    val = default
    try:
        for line in open(SETT):
            if line.startswith(key + "="): val = line.strip().split("=", 1)[1]
    except FileNotFoundError: pass
    return val

def categorize(name, port):
    lc = (name or "").lower()
    if "metro" in lc: return "metro"
    if "admin" in lc: return "admin"
    if "backend" in lc or lc.endswith("-api"): return "backend"
    if port in ("8000", "8001", "8080"): return "backend"
    if port in [str(p) for p in range(8082, 8092)]: return "metro"
    if "landing" in lc or "portfolio" in lc or "website" in lc: return "landing"
    if port == "-": return "other"
    return "web"

def port_up(port):
    if not port.isdigit(): return None
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(0.12)
    try: return s.connect_ex(("127.0.0.1", int(port))) == 0
    except Exception: return False
    finally: s.close()

def status():
    favs = set(read_favorites()); projs = []
    for p in read_projects():
        projs.append({**p, "cat": categorize(p["name"], p["port"]),
                      "running": port_up(p["port"]), "favorite": p["name"] in favs})
    projs.sort(key=lambda x: (CAT_ORDER.index(x["cat"]) if x["cat"] in CAT_ORDER else 9, x["name"]))
    return {"projects": projs, "favorites": sorted(favs),
            "settings": {"placement": get_setting("placement", "on"), "tile": get_setting("tile", "on")},
            "cat_label": CAT_LABEL, "cat_order": CAT_ORDER}

def _yq(args):
    try: return json.loads(subprocess.check_output(["yabai","-m","query"]+args, stderr=subprocess.DEVNULL))
    except Exception: return []

def _space_ordinals():
    # -> {space_index: (display, ordinal-among-real-desktops)} for non-fullscreen spaces
    spc = _yq(["--spaces"]); byd = defaultdict(list); info = {}
    for s in sorted(spc, key=lambda s: s["index"]): byd[s["display"]].append(s)
    for d, sl in byd.items():
        o = 0
        for s in sl:
            if not s.get("is-native-fullscreen"): o += 1; info[s["index"]] = (d, o)
    return info

def layout():
    disp = _yq(["--displays"]); spc = _yq(["--spaces"]); win = _yq(["--windows"])
    markers = {p["name"]: p["port"] for p in read_projects()}
    favs = set(read_favorites())
    ordinals = _space_ordinals()
    def marker_of(w):
        if w.get("app") != "Terminal": return None
        t = w.get("title") or ""
        for m in markers:
            if m in t: return m
        return None
    out_disp = []
    for d in disp:
        f = d["frame"]
        out_disp.append({"index": d["index"], "x": int(f["x"]), "y": int(f["y"]),
                         "w": int(f["w"]), "h": int(f["h"]),
                         "orientation": "portrait" if f["h"] > f["w"] else "landscape"})
    out_spc = []
    for s in spc:
        oi = ordinals.get(s["index"])
        out_spc.append({"index": s["index"], "display": s["display"],
                        "fullscreen": bool(s.get("is-native-fullscreen")),
                        "ordinal": oi[1] if oi else None})
    out_win = []
    for w in win:
        if w.get("is-minimized") or w.get("is-hidden"): continue
        f = w.get("frame", {}); mk = marker_of(w)
        cat = categorize(mk, markers.get(mk, "-")) if mk else None
        out_win.append({"id": w["id"], "app": w.get("app", ""), "marker": mk, "cat": cat,
                        "fav": mk in favs if mk else False,
                        "x": int(f.get("x", 0)), "y": int(f.get("y", 0)),
                        "w": int(f.get("w", 0)), "h": int(f.get("h", 0)),
                        "space": w.get("space"), "display": w.get("display"),
                        "fullscreen": bool(w.get("is-native-fullscreen")),
                        "focus": bool(w.get("has-focus"))})
    return {"displays": out_disp, "spaces": out_spc, "windows": out_win,
            "cat_order": CAT_ORDER, "cat_label": CAT_LABEL}

def arrange(moves):
    # moves: [{id, marker, space}]  -- space = target yabai space index
    for m in moves:
        try:
            subprocess.run(["yabai","-m","window",str(m["id"]),"--space",str(m["space"])],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except Exception: pass
    # persist perch-terminal overrides to spaces.conf as marker|display:ordinal
    info = _space_ordinals()
    try: lines = open(SPACES).read().splitlines()
    except FileNotFoundError: lines = []
    def set_override(marker, spec):
        kept = [l for l in lines
                if not (l.strip() and not l.strip().startswith("#") and l.split("|")[0].strip() == marker)]
        kept.append("%s|%s" % (marker, spec)); return kept
    for m in moves:
        mk = m.get("marker")
        if mk and m["space"] in info:
            d, o = info[m["space"]]; lines = set_override(mk, "%d:%d" % (d, o))
    try:
        with open(SPACES, "w") as fh: fh.write("\n".join(lines) + "\n")
    except Exception: pass
    run_perch(["place", "fav"], wait=True)
    return True

def run_perch(args, wait=False):
    try:
        pr = subprocess.Popen([PERCH] + args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if wait: pr.wait(timeout=30)
        return True
    except Exception: return False

def _favremove(name):
    favs = [f for f in read_favorites() if f != name]
    try:
        with open(FAV, "w") as fh: fh.write("\n".join(favs) + ("\n" if favs else ""))
    except Exception: pass
    return True

def pick_folder():
    # native macOS folder chooser; the GUI runs locally so we can return the real path
    default = HOME + "/Documents/Programming-Codes"
    loc = ' default location (POSIX file "%s")' % default if os.path.isdir(default) else ""
    choose = 'POSIX path of (choose folder with prompt "Select the project folder"%s)' % loc
    try:
        out = subprocess.check_output(
            ["osascript", "-e", 'tell application "System Events" to activate', "-e", choose],
            stderr=subprocess.DEVNULL, timeout=180).decode().strip()
    except subprocess.CalledProcessError:
        return {"cancelled": True}          # user hit Cancel
    except Exception as e:
        return {"error": str(e)}
    if not out:
        return {"cancelled": True}
    out = out.rstrip("/")
    return {"path": out, "name": os.path.basename(out)}

def add_project(d):
    name = (d.get("name") or "").strip()
    port = ((d.get("port") or "").strip() or "-")
    folder = (d.get("dir") or "").strip()
    cmd = (d.get("cmd") or "").strip()
    if not name or not folder or not cmd:
        return {"ok": False, "error": "name, folder and start command are all required"}
    if "|" in name or "|" in folder or "|" in cmd:
        return {"ok": False, "error": "the '|' character is not allowed"}
    if not os.path.isdir(os.path.expanduser(folder)):
        return {"ok": False, "error": "folder does not exist: " + folder}
    if any(p["name"] == name for p in read_projects()):
        return {"ok": False, "error": "a project named '%s' already exists" % name}
    try:
        r = subprocess.run([PERCH, "add", name, port, folder, cmd],
                           capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return {"ok": False, "error": (r.stderr or r.stdout or "perch add failed").strip()}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "name": name}

ACTIONS = {
    "start":     lambda d: run_perch([d["name"]]),
    "stop":      lambda d: run_perch(["stop", d["name"]], wait=True),
    "startall":  lambda d: run_perch(["fav", "go"]),
    "stopall":   lambda d: run_perch(["killall"], wait=True),
    "stopclose": lambda d: run_perch(["killall", "--close"], wait=True),
    "place":     lambda d: run_perch(["place", "fav"], wait=True),
    "favadd":    lambda d: run_perch(["fav", "add", d["name"]], wait=True),
    "favremove": lambda d: _favremove(d["name"]),
}

class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"): self._send(200, HTML, "text/html; charset=utf-8")
        elif self.path.startswith("/api/status"): self._send(200, json.dumps(status()))
        elif self.path.startswith("/api/layout"): self._send(200, json.dumps(layout()))
        elif self.path.startswith("/api/pickfolder"): self._send(200, json.dumps(pick_folder()))
        else: self._send(404, "{}")
    def do_POST(self):
        ln = int(self.headers.get("Content-Length", "0"))
        try: d = json.loads(self.rfile.read(ln) or "{}")
        except Exception: d = {}
        if self.path.startswith("/api/action"):
            act = d.get("action", "")
            if act == "toggle": run_perch(["set", d.get("key", ""), d.get("val", "")], wait=True)
            elif act in ACTIONS: ACTIONS[act](d)
            self._send(200, json.dumps({"ok": True}))
        elif self.path.startswith("/api/arrange"):
            arrange(d.get("moves", [])); self._send(200, json.dumps({"ok": True}))
        elif self.path.startswith("/api/addproject"):
            self._send(200, json.dumps(add_project(d)))
        else: self._send(404, "{}")
    def log_message(self, *a): pass

class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True; allow_reuse_address = True

HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>perch</title>
<style>
:root{
  --bg:oklch(0.17 0.013 260); --bg2:oklch(0.21 0.014 260); --surf:oklch(0.235 0.016 260);
  --surf2:oklch(0.28 0.018 260); --line:oklch(0.33 0.02 260); --line2:oklch(0.42 0.025 260);
  --tx:oklch(0.95 0.006 260); --dim:oklch(0.72 0.02 260); --faint:oklch(0.55 0.02 260);
  --acc:oklch(0.72 0.15 255);
  --metro:oklch(0.72 0.16 32); --landing:oklch(0.80 0.14 90); --web:oklch(0.76 0.13 168);
  --backend:oklch(0.72 0.15 258); --admin:oklch(0.74 0.16 322); --other:oklch(0.66 0.02 260);
  --grn:oklch(0.78 0.17 150); --red:oklch(0.68 0.2 25);
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:radial-gradient(120% 90% at 50% -10%, oklch(0.2 0.02 262), var(--bg) 60%);
  color:var(--tx);font:14px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
header{position:sticky;top:0;z-index:20;background:oklch(0.17 0.013 260 / .82);backdrop-filter:blur(14px) saturate(1.2);
  border-bottom:1px solid var(--line);padding:12px 22px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
h1{font-size:15px;margin:0;font-weight:680;letter-spacing:.2px;display:flex;align-items:center;gap:9px}
.sub{color:var(--dim);font-size:12.5px}
.spacer{flex:1}
.seg{display:inline-flex;background:var(--bg2);border:1px solid var(--line);border-radius:10px;padding:3px}
.seg button{border:0;background:transparent;color:var(--dim);padding:6px 14px;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer;transition:color .15s}
.seg button.on{background:var(--surf2);color:var(--tx);box-shadow:0 1px 2px oklch(0 0 0 /.35)}
.btn{border:1px solid var(--line);background:var(--surf);color:var(--tx);padding:7px 13px;border-radius:9px;font-size:13px;font-weight:600;cursor:pointer;transition:.13s cubic-bezier(.2,.7,.3,1)}
.btn:hover{border-color:var(--line2);background:var(--surf2);transform:translateY(-1px)}
.btn.primary{background:var(--acc);border-color:transparent;color:oklch(0.16 0.03 260)}
.btn.primary:hover{filter:brightness(1.07)}
.btn.danger:hover{border-color:var(--red);color:var(--red)}
.btn:disabled{opacity:.4;cursor:default;transform:none}
.toggle{display:inline-flex;align-items:center;gap:8px;font-size:12px;color:var(--dim);user-select:none;cursor:pointer}
.sw{width:34px;height:20px;border-radius:999px;background:var(--line2);position:relative;transition:.18s cubic-bezier(.2,.7,.3,1);flex:none}
.sw.on{background:var(--grn)}
.sw i{position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:oklch(0.98 0.005 260);transition:.18s cubic-bezier(.2,.7,.3,1)}
.sw.on i{transform:translateX(14px)}
main{max-width:1180px;margin:0 auto;padding:22px}
/* ---- servers list ---- */
.group{margin:24px 0 9px;color:var(--dim);font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;display:flex;align-items:center;gap:9px}
.count{background:var(--surf);border:1px solid var(--line);border-radius:20px;padding:1px 8px;font-size:11px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(305px,1fr));gap:10px}
.card{background:var(--surf);border:1px solid var(--line);border-radius:12px;padding:11px 14px;display:flex;align-items:center;gap:12px;transition:border-color .13s}
.card:hover{border-color:var(--line2)}
.dot{width:9px;height:9px;border-radius:50%;background:var(--faint);flex:none}
.dot.up{background:var(--grn);box-shadow:0 0 11px oklch(0.78 0.17 150 /.7)}
.dot.na{background:var(--line2)}
.meta{flex:1;min-width:0}.nm{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pt{color:var(--dim);font-size:12px}
.star{cursor:pointer;color:var(--line2);font-size:15px;transition:.12s}.star.on{color:var(--landing)}
.act{border:1px solid var(--line);background:transparent;color:var(--tx);width:72px;padding:6px 0;border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;transition:.12s}
.act.run{color:var(--grn);border-color:oklch(0.78 0.17 150 /.4)}.act.run:hover{background:oklch(0.78 0.17 150 /.12)}
.act.stopd:hover{background:oklch(0.72 0.15 255 /.14);border-color:var(--acc)}
/* ---- layout view ---- */
.hint{color:var(--dim);font-size:12.5px;margin:2px 0 18px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.legend{display:flex;gap:12px;flex-wrap:wrap;margin-left:auto}
.lg{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;color:var(--dim)}
.lg i{width:10px;height:10px;border-radius:3px;display:inline-block}
.minimap{display:flex;align-items:center;gap:10px;background:var(--bg2);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:20px;position:relative;overflow:hidden}
.mm-box{position:relative;border:1px solid var(--line2);border-radius:4px;background:var(--surf)}
.mm-box b{position:absolute;left:5px;top:3px;font-size:9px;color:var(--faint);font-weight:600}
.displays{display:flex;flex-direction:column;gap:26px}
.disprow{}
.disphead{display:flex;align-items:baseline;gap:10px;margin-bottom:10px}
.disphead .dt{font-weight:680;font-size:14px}
.disphead .dm{color:var(--dim);font-size:12px}
.orient{font-size:11px;color:var(--faint);border:1px solid var(--line);border-radius:6px;padding:1px 7px}
.desks{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}
.desk{display:flex;flex-direction:column;gap:7px}
.desk .dl{font-size:11.5px;color:var(--dim);font-weight:600;display:flex;align-items:center;gap:6px}
.desk .dl .badge{background:var(--surf);border:1px solid var(--line);border-radius:6px;padding:0 6px;font-size:10.5px;color:var(--faint)}
.screen{position:relative;background:
  linear-gradient(oklch(0.14 0.012 260),oklch(0.155 0.013 260));
  border:1px solid var(--line);border-radius:8px;overflow:hidden;transition:box-shadow .15s,border-color .15s}
.screen.drop{border-color:var(--acc);box-shadow:0 0 0 3px oklch(0.72 0.15 255 /.28) inset}
.screen.fs{display:flex;align-items:center;justify-content:center;
  background:repeating-linear-gradient(45deg,oklch(0.19 0.014 260),oklch(0.19 0.014 260) 7px,oklch(0.21 0.016 260) 7px,oklch(0.21 0.016 260) 14px)}
.fslabel{color:var(--dim);font-size:11px;text-align:center;padding:6px;line-height:1.35}
.win{position:absolute;border-radius:3px;overflow:hidden;display:flex;align-items:flex-start;font-size:9px;line-height:1.15;
  padding:2px 3px;color:oklch(0.98 0.01 260);border:1px solid oklch(1 0 0 /.14);transition:transform .12s,box-shadow .12s}
.win.other{background:oklch(0.3 0.012 260 /.72);color:var(--dim);border-color:oklch(1 0 0 /.06)}
.win.term{cursor:grab;box-shadow:0 1px 3px oklch(0 0 0 /.4)}
.win.term:hover{box-shadow:0 3px 10px oklch(0 0 0 /.5);z-index:3}
.win.term.stopd{opacity:.55;filter:saturate(.5)}
.win .wl{font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:100%}
.win .wd{position:absolute;right:2px;top:2px;width:5px;height:5px;border-radius:50%;background:var(--grn);box-shadow:0 0 5px var(--grn)}
.win.dragging{opacity:.25}
.ghost{position:fixed;z-index:99;pointer-events:none;border-radius:4px;padding:3px 7px;font-size:11px;font-weight:650;
  color:oklch(0.99 0.01 260);box-shadow:0 8px 24px oklch(0 0 0 /.5);border:1px solid oklch(1 0 0 /.25);will-change:transform}
.savebar{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(140%);z-index:40;
  display:flex;align-items:center;gap:14px;background:var(--surf2);border:1px solid var(--line2);border-radius:14px;
  padding:11px 14px 11px 18px;box-shadow:0 14px 40px oklch(0 0 0 /.5);transition:transform .32s cubic-bezier(.2,.8,.2,1)}
.savebar.show{transform:translateX(-50%) translateY(0)}
.savebar .msg{font-size:13px}.savebar .msg b{color:var(--acc)}
.foot{color:var(--faint);font-size:11px;text-align:center;padding:26px 0 60px}
.empty{color:var(--dim);text-align:center;padding:60px 20px}
/* ---- add-project modal ---- */
.modal{position:fixed;inset:0;z-index:60;display:none;align-items:center;justify-content:center;background:oklch(0 0 0 /.55);backdrop-filter:blur(4px)}
.modal.show{display:flex}
.sheet{background:var(--surf2);border:1px solid var(--line2);border-radius:16px;padding:22px 22px 20px;width:min(470px,92vw);box-shadow:0 24px 70px oklch(0 0 0 /.6)}
.sheet h2{margin:0 0 4px;font-size:16px;font-weight:680}
.sheet .desc{color:var(--dim);font-size:12.5px;margin-bottom:8px}
.sheet label{display:block;font-size:11px;color:var(--dim);font-weight:700;margin:13px 0 5px;text-transform:uppercase;letter-spacing:.5px}
.in{width:100%;background:var(--bg2);border:1px solid var(--line);border-radius:9px;padding:9px 11px;color:var(--tx);font-size:13px;font-family:inherit}
.in:focus{outline:none;border-color:var(--acc)}
.in[readonly]{color:var(--dim);cursor:default}
.rowf{display:flex;gap:8px}.rowf .in{flex:1}
.row2{display:flex;gap:12px}.row2 .col-port{width:150px}.row2 .col-cmd{flex:1}
.rowend{display:flex;justify-content:flex-end;gap:10px;margin-top:20px}
.aperr{color:var(--red);font-size:12.5px;margin-top:11px;min-height:16px}
.aperr.info{color:var(--dim)}
</style></head><body>
<header>
  <h1>🪺 perch</h1>
  <span class="sub" id="sub">-</span>
  <span class="spacer"></span>
  <span class="seg"><button id="tab-layout" class="on" onclick="setView('layout')">Layout</button><button id="tab-servers" onclick="setView('servers')">Servers</button></span>
  <span class="toggle" onclick="tog('placement')">placement <span class="sw" id="sw-placement"><i></i></span></span>
  <span class="toggle" onclick="tog('tile')">tile <span class="sw" id="sw-tile"><i></i></span></span>
  <button class="btn" onclick="openAdd()">＋ Add project</button>
  <button class="btn primary" onclick="act('startall')">Start favorites ▸</button>
</header>
<main id="main"></main>
<div class="foot" id="foot"></div>
<div class="savebar" id="savebar">
  <span class="msg" id="savemsg"></span>
  <button class="btn" onclick="revert()">Revert</button>
  <button class="btn primary" onclick="save()">Save changes</button>
</div>
<div class="modal" id="addModal" onclick="if(event.target===this)closeAdd()">
  <div class="sheet">
    <h2>Add a project</h2>
    <div class="desc">Register a project so you can launch it from perch by name.</div>
    <label>Project folder</label>
    <div class="rowf">
      <input id="ap-dir" class="in" placeholder="Pick the project folder…" readonly>
      <button class="btn" onclick="browseFolder()">Browse…</button>
    </div>
    <label>Name</label>
    <input id="ap-name" class="in" placeholder="my-project">
    <div class="row2">
      <div class="col-port"><label>Port</label><input id="ap-port" class="in" placeholder="3000  ( - = none )"></div>
      <div class="col-cmd"><label>Start command</label><input id="ap-cmd" class="in" placeholder="e.g. npm run dev"></div>
    </div>
    <div class="aperr" id="ap-err"></div>
    <div class="rowend">
      <button class="btn" onclick="closeAdd()">Cancel</button>
      <button class="btn primary" id="ap-submit" onclick="submitAdd()">Add project</button>
    </div>
  </div>
</div>
<script>
let VIEW='layout', S=null, L=null, PENDING={}; // marker -> new space index
const CATVAR={metro:'--metro',landing:'--landing',web:'--web',backend:'--backend',admin:'--admin',other:'--other'};
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function cvar(c){return `var(${CATVAR[c]||'--other'})`;}
async function loadStatus(){ S=await (await fetch('/api/status')).json(); if(VIEW==='servers')renderServers(); syncHeader(); }
async function loadLayout(){ L=await (await fetch('/api/layout')).json(); if(VIEW==='layout')renderLayout(); }
function syncHeader(){
  if(!S)return;
  document.getElementById('sw-placement').className='sw'+(S.settings.placement==='on'?' on':'');
  document.getElementById('sw-tile').className='sw'+(S.settings.tile==='on'?' on':'');
  const up=S.projects.filter(p=>p.running).length;
  document.getElementById('sub').textContent=`${S.projects.length} projects · ${up} running · ${S.favorites.length} favorites`;
}
async function act(action,extra){ await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...extra})}); setTimeout(refresh,600); if(action==='startall'){setTimeout(refresh,4000);setTimeout(refresh,8000);} }
function tog(key){ const cur=S.settings[key]; act('toggle',{key,val:cur==='on'?'off':'on'}); }
function setView(v){ VIEW=v; document.getElementById('tab-layout').className=v==='layout'?'on':''; document.getElementById('tab-servers').className=v==='servers'?'on':''; refresh(); }
function refresh(){ loadStatus(); loadLayout(); }

/* ---------- servers list ---------- */
function renderServers(){
  const byCat={}; S.projects.forEach(p=>{(byCat[p.cat]=byCat[p.cat]||[]).push(p);});
  let h='';
  S.cat_order.forEach(cat=>{ const list=byCat[cat]; if(!list)return;
    h+=`<div class="group"><span style="width:9px;height:9px;border-radius:3px;background:${cvar(cat)}"></span>${esc(S.cat_label[cat]||cat)}<span class="count">${list.length}</span></div><div class="grid">`;
    list.forEach(p=>{
      const dot=p.running===true?'up':(p.running===null?'na':'');
      const label=p.running?'Stop':'Start', action=p.running?'stop':'start';
      h+=`<div class="card"><span class="dot ${dot}"></span>
        <span class="meta"><div class="nm">${esc(p.name)}</div><div class="pt">${p.port==='-'?'no port':':'+esc(p.port)}</div></span>
        <span class="star ${p.favorite?'on':''}" onclick='act("${p.favorite?"favremove":"favadd"}",{name:${JSON.stringify(p.name)}})'>${p.favorite?'★':'☆'}</span>
        <button class="act ${p.running?'run':'stopd'}" onclick='act("${action}",{name:${JSON.stringify(p.name)}})'>${label}</button></div>`;
    });
    h+='</div>';
  });
  document.getElementById('main').innerHTML=h;
  document.getElementById('foot').textContent='perch · localhost · auto-refreshing';
}

/* ---------- layout / spatial arranger ---------- */
function spaceOf(marker, fallback){ return (marker in PENDING)?PENDING[marker]:fallback; }
function renderLayout(){
  if(!L||!L.displays.length){ document.getElementById('main').innerHTML='<div class="empty">Waiting for yabai…</div>'; return; }
  // minimap: displays to real relative scale
  const xs=L.displays.map(d=>d.x), ys=L.displays.map(d=>d.y);
  const minx=Math.min(...xs), miny=Math.min(...ys);
  const maxx=Math.max(...L.displays.map(d=>d.x+d.w)), maxy=Math.max(...L.displays.map(d=>d.y+d.h));
  const mmScale=Math.min(300/(maxx-minx), 92/(maxy-miny));
  let mm=`<div class="minimap" style="height:${(maxy-miny)*mmScale+28}px"><div style="position:relative;width:${(maxx-minx)*mmScale}px;height:${(maxy-miny)*mmScale}px;margin:auto">`;
  L.displays.forEach(d=>{ mm+=`<div class="mm-box" style="left:${(d.x-minx)*mmScale}px;top:${(d.y-miny)*mmScale}px;width:${d.w*mmScale}px;height:${d.h*mmScale}px"><b>${d.orientation==='portrait'?'▯':'▭'} ${d.w}×${d.h}</b></div>`; });
  mm+=`</div><div style="margin-left:8px"><div class="hint" style="margin:0">Your screens, to scale.</div><div class="legend">`+
    L.cat_order.map(c=>`<span class="lg"><i style="background:${cvar(c)}"></i>${esc(L.cat_label[c]||c)}</span>`).join('')+
    `<span class="lg"><i style="background:oklch(0.3 0.012 260)"></i>other apps</span></div></div></div>`;

  // group spaces by display, ordered
  const spByDisp={}; L.spaces.forEach(s=>{(spByDisp[s.display]=spByDisp[s.display]||[]).push(s);});
  Object.values(spByDisp).forEach(a=>a.sort((x,y)=>x.index-y.index));
  const dOrder=L.displays.slice().sort((a,b)=>a.x-b.x); // left-to-right physical order

  let h=mm+`<div class="hint">Drag a terminal to another desktop, then <b style="color:var(--acc)">Save</b>. Greyed tiles are other apps and fullscreen spaces, shown for context.</div><div class="displays">`;
  dOrder.forEach(d=>{
    const spaces=(spByDisp[d.index]||[]);
    // canvas scale: fit each desktop into a box preserving the display aspect
    const cap = d.orientation==='portrait'?238:250;
    const sc = Math.min(cap/d.w, 238/d.h);
    const cw=Math.round(d.w*sc), ch=Math.round(d.h*sc);
    h+=`<div class="disprow"><div class="disphead"><span class="dt">Display ${d.index}</span><span class="orient">${d.orientation}</span><span class="dm">${d.w}×${d.h}</span></div><div class="desks">`;
    let realIdx=0;
    spaces.forEach(s=>{
      const wins=L.windows.filter(w=>spaceOf(w.marker, w.space)===s.index || (w.marker&&PENDING[w.marker]===s.index));
      const deskNo = s.fullscreen?null:(++realIdx);
      const label = s.fullscreen?`fullscreen`:`Desktop ${deskNo}`;
      h+=`<div class="desk"><div class="dl">${esc(label)}${s.fullscreen?'':`<span class="badge">${wins.filter(w=>w.marker).length} term</span>`}</div>`;
      if(s.fullscreen){
        const app=(L.windows.find(w=>w.space===s.index)||{}).app||'—';
        h+=`<div class="screen fs" style="width:${cw}px;height:${ch}px"><div class="fslabel">⛶<br>${esc(app)}</div></div>`;
      } else {
        h+=`<div class="screen" data-space="${s.index}" data-disp="${d.index}" style="width:${cw}px;height:${ch}px">`;
        wins.forEach(w=>{
          const left=Math.max(0,(w.x-d.x)*sc), top=Math.max(0,(w.y-d.y)*sc);
          const ww=Math.max(10,Math.min(cw-left,w.w*sc)), wh=Math.max(9,Math.min(ch-top,w.h*sc));
          if(w.marker){
            const proj=(S?S.projects.find(p=>p.name===w.marker):null);
            const running=proj?proj.running:false;
            h+=`<div class="win term ${running?'':'stopd'}" data-marker="${esc(w.marker)}" data-id="${w.id}"
              style="left:${left}px;top:${top}px;width:${ww}px;height:${wh}px;background:color-mix(in oklch, ${cvar(w.cat)} 82%, black)">
              <span class="wl">${esc(w.marker)}</span>${running?'<span class="wd"></span>':''}</div>`;
          } else {
            h+=`<div class="win other" style="left:${left}px;top:${top}px;width:${ww}px;height:${wh}px"><span class="wl">${esc(w.app)}</span></div>`;
          }
        });
        h+=`</div>`;
      }
      h+=`</div>`;
    });
    h+=`</div></div>`;
  });
  h+=`</div>`;
  document.getElementById('main').innerHTML=h;
  document.getElementById('foot').textContent='perch spatial arranger · drag terminals between desktops';
  wireDrag();
  updateSaveBar();
}

/* pointer drag: terminal tile -> desktop screen */
let drag=null;
function wireDrag(){
  document.querySelectorAll('.win.term').forEach(el=>{
    el.addEventListener('pointerdown',e=>{
      e.preventDefault();
      const marker=el.dataset.marker, id=+el.dataset.id;
      const ghost=document.createElement('div'); ghost.className='ghost';
      const cat=(S?.projects.find(p=>p.name===marker)||{}).cat||'other';
      ghost.style.background=`color-mix(in oklch, var(${CATVAR[cat]||'--other'}) 82%, black)`;
      ghost.textContent=marker; document.body.appendChild(ghost);
      drag={marker,id,ghost,el}; el.classList.add('dragging');
      moveGhost(e); document.addEventListener('pointermove',onMove); document.addEventListener('pointerup',onUp);
    });
  });
}
function moveGhost(e){ if(drag)drag.ghost.style.transform=`translate(${e.clientX+12}px,${e.clientY+8}px)`; }
function onMove(e){ moveGhost(e);
  document.querySelectorAll('.screen.drop').forEach(s=>s.classList.remove('drop'));
  const t=document.elementFromPoint(e.clientX,e.clientY)?.closest('.screen[data-space]');
  if(t)t.classList.add('drop');
}
function onUp(e){
  document.removeEventListener('pointermove',onMove); document.removeEventListener('pointerup',onUp);
  const t=document.elementFromPoint(e.clientX,e.clientY)?.closest('.screen[data-space]');
  if(drag){ drag.ghost.remove(); drag.el.classList.remove('dragging'); }
  if(t&&drag){
    const newSpace=+t.dataset.space;
    const win=L.windows.find(w=>w.marker===drag.marker);
    const curSpace=spaceOf(drag.marker, win?win.space:newSpace);
    if(newSpace!==curSpace){ PENDING[drag.marker]=newSpace; renderLayout(); }
  }
  drag=null;
}
function updateSaveBar(){
  const n=Object.keys(PENDING).length, bar=document.getElementById('savebar');
  document.getElementById('savemsg').innerHTML = n?`<b>${n}</b> terminal${n>1?'s':''} to move`:'';
  bar.className='savebar'+(n?' show':'');
}
function revert(){ PENDING={}; renderLayout(); }
async function save(){
  const moves=Object.entries(PENDING).map(([marker,space])=>{
    const w=L.windows.find(x=>x.marker===marker); return {marker,id:w?w.id:0,space};
  }).filter(m=>m.id);
  document.getElementById('savemsg').innerHTML='saving…';
  await fetch('/api/arrange',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({moves})});
  PENDING={}; setTimeout(()=>{refresh();},700); setTimeout(refresh,2500);
}
/* ---------- add project ---------- */
function apErr(msg,info){ const e=document.getElementById('ap-err'); e.textContent=msg||''; e.className='aperr'+(info?' info':''); }
function openAdd(){ ['ap-dir','ap-name','ap-port','ap-cmd'].forEach(id=>document.getElementById(id).value=''); apErr(''); document.getElementById('addModal').classList.add('show'); }
function closeAdd(){ document.getElementById('addModal').classList.remove('show'); }
async function browseFolder(){
  apErr('opening folder picker…',true);
  let r; try{ r=await (await fetch('/api/pickfolder')).json(); }catch(e){ apErr('could not open picker'); return; }
  if(r.cancelled){ apErr(''); return; }
  if(r.error){ apErr(r.error); return; }
  apErr('');
  document.getElementById('ap-dir').value=r.path;
  if(!document.getElementById('ap-name').value.trim()) document.getElementById('ap-name').value=r.name||'';
  document.getElementById('ap-cmd').focus();
}
async function submitAdd(){
  const dir=document.getElementById('ap-dir').value.trim();
  const name=document.getElementById('ap-name').value.trim();
  const port=document.getElementById('ap-port').value.trim()||'-';
  const cmd=document.getElementById('ap-cmd').value.trim();
  if(!dir) return apErr('Pick a project folder first.');
  if(!name) return apErr('Enter a name.');
  if(!cmd) return apErr('Enter a start command.');
  const btn=document.getElementById('ap-submit'); btn.disabled=true; apErr('adding…',true);
  let r; try{ r=await (await fetch('/api/addproject',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,port,dir,cmd})})).json(); }
  catch(e){ btn.disabled=false; return apErr('request failed'); }
  btn.disabled=false;
  if(!r.ok) return apErr(r.error||'failed to add');
  closeAdd(); setView('servers'); setTimeout(refresh,300);
}
document.addEventListener('keydown',e=>{ if(e.key==='Escape')closeAdd(); });

loadStatus(); loadLayout();
setInterval(()=>{ if(!drag&&Object.keys(PENDING).length===0) refresh(); }, 4000);
</script></body></html>"""

if __name__ == "__main__":
    try:
        Server(("127.0.0.1", PORT), Handler).serve_forever()
    except OSError as e:
        print("perch-gui: %s" % e)
