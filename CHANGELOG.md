# Changelog

## 2.3.0

Product clusters, prefix launch, port resolution, nested help, and dashboard project-add.

### Added
- **`perch port [name]`**: print the assigned port for a project — by name, or resolved from the current directory. Meant for a project's own start script, so `yarn dev` binds the perch port when perch is installed and the framework default otherwise: `next dev -p $(perch port 2>/dev/null || echo 3000)`.
- **Product clusters**: `perch groups` lists projects auto-grouped by product (the name up to the first `-`), with ports and live status. Each multi-project cluster shows how to start it all at once.
- **Prefix launch**: `perch <prefix>` — e.g. `perch jakstoc` (or quoted `perch 'jakstoc*'`) — starts every matching project, backend first.
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
