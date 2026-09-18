# Changelog

## 2.7.0

### Added — herd your coding agents (tmux-backed)
- **`perch agent <name> [dir] [command]`**: launch a coding agent (Claude Code, Codex, Cursor, opencode, aider, …) as a window in one persistent tmux session. It survives closing Terminal — reattach any time. Omit the command and perch runs the first agent CLI it finds installed. Reusing a name focuses the existing agent instead of double-starting it.
- **`perch agents`**: list every agent with a live status — **● working** (recent output), **● blocked** (a question/permission prompt is waiting on you), or **● idle** — so you never hunt for the stuck one. `--plain` for scripts, `--count` for the `▶ ⏸ ⚠` tallies.
- **`perch cockpit`**: attach the whole herd as tabs in ONE terminal, with a themed status bar (perch badge, live working/idle/blocked counts, the current agent tab highlighted). Mouse-clickable tabs; switch with the tmux keys.
- **`perch agent stop|restart <name>`**, **`perch agents stop [name] | killall`**, **`perch agents detect`** (list the agent CLIs installed on this machine).
- **Menu bar (PerchBar)**: a new **Agents** section shows each agent with its status dot, a **blocked** badge, per-agent restart/stop, and an **Open cockpit** row. When any agent is blocked, the menu bar itself shows a **⚠N** so you notice from anywhere.
- Requires `tmux` (`brew install tmux`).

### Changed
- The park toggle in the menu bar now reads **"Park windows when a monitor unplugs"** (it always covered pinned apps too, not just terminals), with a clearer subtext and a **"See how windows are organized"** link that opens the dashboard. Matching wording fixed in `perch park`/`unpark` help.

### Added — per-window park exemption (apps AND terminals)
- **`perch apps park "<name>" on|off`**: exempt a single window from parking — works for a pinned app *or* a perch terminal (by its marker). With it **off**, that window stays put when a monitor disconnects instead of being minimized with everything else. State persists in `~/.config/perch/park-exclude` and is respected by both manual and automatic park; it shows in `perch apps list` and in `perch list --plain` (a 5th `on/off` column).
- **Menu bar (PerchBar)**: a redesigned **"Keep in place"** area under the park toggle — pinned apps render as cards with their real app icons, and a **Terminals** disclosure expands to let you de-pin any open terminal. Flip one off and the card turns amber with a 📌, reading "stays in place on disconnect."

## 2.6.0

### Added
- **Park on monitor disconnect**: `perch park` minimizes every terminal that is mapped to an external display but got dumped onto the main (laptop) display when that monitor disconnected, so the laptop screen stays clean. `perch unpark` restores them and re-places them. Autoplace now wires a `display_removed` yabai signal to `park`, and its `display_added` handler unparks before placing — so disconnect/reconnect is fully automatic. Uses the window's real display (not display indices), so it stays correct when yabai renumbers displays after a middle monitor drops.
- **Menu bar (toolbar) app**: `perch bar` builds and launches PerchBar, a native zero-dependency NSStatusItem app (🪶 with a running-server count). Compact top level: **Running servers ▸** (each server has Restart / Open in browser / Stop), **Start a project ▸** (all projects grouped by type), a **Park terminals when a monitor unplugs** checkmark toggle, **Open web dashboard**, plus Place all / Launch favorites / Stop all. `perch bar on/off` adds/removes it from login; `perch bar build` rebuilds from `perch-bar.swift`.
- **`perch set park on|off`**: turn the automatic park-on-monitor-unplug behavior off/on (default on). Manual `perch park` always works; only the signal-driven park respects it. `perch set <key>` with no value prints the current value.
- **Pin other apps to a display, not just terminals**: `perch apps add "Google Chrome" 2:1` maps any app to a `display:space`; `perch place` then sends that app's windows there too, and park/unpark cover them on monitor disconnect/reconnect. `perch apps list|remove` to manage the map (`~/.config/perch/apps.conf`).
- **Menu bar net speed (NetSpeed-style)**: the menu bar item now shows live ↓/↑ throughput next to the 🪶 and running-server count, sampled from the active interfaces every 1.5s.
- **App icon**: PerchBar now ships a generated icon (bird on a teal squircle) built from `perch-icon.swift` at `perch bar build` time.
- **Faster menu**: `perch list --plain` went from ~2.3s to ~0.02s (one `netstat` for all ports instead of one `lsof` per project; fork-free `categorize`), and the menu bar app caches state + refreshes in the background so the panel opens instantly.
- **`perch list --plain`**: tab-separated `name port status category` for scripts and the menu bar app.

## 2.5.4

### Added
- **Metro appends client logs**: Metro servers now tee their output — which includes the React Native app's client `console.log` — to a per-marker logfile at `~/.config/perch/logs/<marker>.log` (append, so it survives restarts). Uses a plain pipe so Metro keeps its interactive TTY (r/reload, d/devmenu still work). Only applies to metro-category servers; everything else launches unchanged.

## 2.5.3

### Added
- **Port in the tab title**: each tab is now titled `<name> - port:<port>`, so you can see which server *and* which port at a glance (port-less projects keep just the name). Tab reuse and `killall --close` matching handle both the old (`<name>`) and new (`<name> - port:<port>`) forms.
- **Restart refreshes the title**: relaunching into an existing tab now updates its title too (previously only freshly-created tabs got it).

## 2.5.2

Health checks, tab completion, URLs/QR, and dependency-aware clusters.

### Added
- **Launch shows URLs**: the confirmation line now prints the network (LAN) + localhost URLs of the started server (⌘-clickable), instead of echoing just the command.
- **Health checks**: `perch <project> --wait` launches, then blocks until the port is actually listening (or 40s). `perch list` / `perch fav list` already mark up / down / stale by port.
- **Dependency-aware clusters**: `perch <prefix>` starts the backend tier first, waits until it's healthy, THEN starts the dependents (web/admin) — no more racing a not-ready API.
- **`perch open [project]`**: open the project's localhost URL in your browser (no arg = the current terminal's project).
- **`perch url [project]`**: print the network + localhost URLs, plus a scannable QR of the network URL (needs `qrencode`) to open the dev server on your phone.
- **`perch completion [zsh|bash]`**: shell tab-completion for command + project names.

## 2.5.1

### Added
- **`perch start` / `perch restart` / `perch run` with no argument** re-run the current terminal's own server. Resolves the project from the tab's perch title (matched by tty), else the registered project matching the working directory. Ctrl+C a server, type `perch restart`, and it relaunches in place — no name needed.

## 2.5.0

Terminal-clearing command and a richer favorites listing.

### Added
- **`perch clear`** (alias `perch cls`): clear the text + scrollback of *every* Terminal tab, like Cmd+K, without stopping anything. Writes the clear escape straight to each tab's tty, so it works even in tabs running a live server (a plain `clear` can't while a process holds the shell).
- **`perch fav list` is now a table**: PROJECT, PORT, STATUS (`up` / `.` / `stale`), TYPE (category), and COMMAND, with a footer showing how many are up. Favorites stored by folder name resolve to their project; ones that no longer resolve show as `stale`.

## 2.4.0

Folder-name resolution, `start`/`restart`, "did you mean" suggestions, and automatic terminal placement.

### Added
- **`perch start <project>` / `perch restart <project>`**: explicit verbs for the launch-in-its-tab behavior, alongside the bare `perch <project>`. All three resolve a project name, a product cluster prefix, or a folder name.
- **Folder-name resolution**: when a token isn't an exact project name or cluster, perch matches it against project directory basenames — so `perch example-mobile` finds the repo registered as `example-metro` living in `.../example-mobile`. Applies to favorites too, so a project favorited by its folder name still launches, places, and stops.
- **"Did you mean" suggestions**: an unknown project, cluster, or command now guesses the closest match (by edit distance across commands + project names) *before* the fallback hints. Mistyped `fav` subcommands get the same treatment.
- **`perch autoplace [on|off|status|now]`**: keep terminals arranged automatically — every new Terminal window or display change re-groups them by type (debounced), persisted to `~/.yabairc` so it survives a yabai restart.
- **`perch place empty`**: spread all open terminals evenly across every free desktop (empty or terminals-only, never a working desktop), ignoring categories — rescues terminals stranded among your other apps.
- **`perch place [category]`**: the default `perch place` now groups *all* open server terminals by type onto their mapped desktops, including unregistered strays.

## 2.3.0

Product clusters, prefix launch, port resolution, nested help, and dashboard project-add.

### Added
- **`perch port [name]`**: print the assigned port for a project — by name, or resolved from the current directory. Meant for a project's own start script, so `yarn dev` binds the perch port when perch is installed and the framework default otherwise: `next dev -p $(perch port 2>/dev/null || echo 3000)`.
- **Product clusters**: `perch groups` lists projects auto-grouped by product (the name up to the first `-`), with ports and live status. Each multi-project cluster shows how to start it all at once.
- **Prefix launch**: `perch <prefix>` — e.g. `perch example` (or quoted `perch 'example*'`) — starts every matching project, backend first.
- **Nested help**: `help` / `-h` / `--help` now works at every level — `perch fav add help`, `perch place help`, `perch help fav`.
- **Dashboard — Add project**: the web dashboard gained an *Add project* button that opens a native folder picker (the real absolute path, since the server is local), auto-fills the name, and registers the project.

## 2.2.1

- The project registry is now kept out of the repo entirely. `projects.conf` is
  gitignored; the repo ships `projects.conf.example` and the installer seeds from
  it. Your project names and paths live only in `~/.config/perch`, never in git.

## 2.2.0

Favorites, multi-monitor placement, a web dashboard, and portability.

### Added
- **Favorites**: `perch fav` (grouped multi-select picker), `perch fav go` (launch the set in category order), and `perch fav set|add|list|clear`.
- **`perch killall`**: stop every running registered server by port; `--close` also closes the tabs (killing each window's tty group first so Terminal does not prompt); `fav` scopes to favorites; `perch stop all` is an alias.
- **Window position memory**: each server's window rectangle (and monitor) is remembered and restored when a fresh window opens; a reused tab is left alone. Inspect with `perch bounds`.
- **Desktop placement + tiling (optional, via yabai)**: send each server to a desktop by category and tile the windows full width, stacked. `perch place [fav] [notile]`. The map lives in `~/.config/perch/spaces.conf` as `display:desktop`, resolved to a live space index at placement time so it survives macOS renumbering spaces when fullscreen apps come and go.
- **`perch setup`**: auto-detect the machine's monitors and write a sensible desktop map. Adapts to 1, 2, 3, or 4+ desktops. A missing map auto-seeds on first `place`.
- **`perch doctor`**: check osascript, python3, yabai (and whether it is responding), settings, registry, and map, with a copy-paste fix under anything that needs one.
- **`perch set`**: persistent settings for `placement` and `tile` (both default on).
- **`perch gui`**: a local web dashboard on `127.0.0.1:7620` (Python standard library, no dependencies). A Servers view (live status, one-click start/stop, favorite toggle) and a Layout view: a to-scale map of your monitors and desktops where you drag terminals between desktops and save.

### Notes
- Everything new is opt-in and degrades gracefully. Without yabai, placement is skipped and the rest works. Without python3, only the dashboard and `perch setup` are unavailable.
- Still macOS only.

## 2.0.0

- Built-in project registry (`~/.config/perch/projects.conf`); launch by name, `perch list`, `perch add`, `perch remove`, `perch stop`.
