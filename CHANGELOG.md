# Changelog

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
- **Folder-name resolution**: when a token isn't an exact project name or cluster, perch matches it against project directory basenames — so `perch jakstoc-mobile` finds the repo registered as `jakstoc-metro` living in `.../jakstoc-mobile`. Applies to favorites too, so a project favorited by its folder name still launches, places, and stops.
- **"Did you mean" suggestions**: an unknown project, cluster, or command now guesses the closest match (by edit distance across commands + project names) *before* the fallback hints. Mistyped `fav` subcommands get the same treatment.
- **`perch autoplace [on|off|status|now]`**: keep terminals arranged automatically — every new Terminal window or display change re-groups them by type (debounced), persisted to `~/.yabairc` so it survives a yabai restart.
- **`perch place empty`**: spread all open terminals evenly across every free desktop (empty or terminals-only, never a working desktop), ignoring categories — rescues terminals stranded among your other apps.
- **`perch place [category]`**: the default `perch place` now groups *all* open server terminals by type onto their mapped desktops, including unregistered strays.

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
