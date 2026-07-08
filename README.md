# perch

Start, restart, and arrange dev servers in named, reusable macOS Terminal tabs.

I run a lot of servers at once: a few Next.js apps, some NestJS backends, four or five Metro bundlers on any given day. The usual way of scripting Terminal from the command line (`osascript ... do script`) opens a brand new window every single time. Restart Metro eight times in an afternoon and you have eight dead windows and no idea which one is live.

perch fixes that. Every server gets a tab with a stable title. Run the same command again and the server restarts in the same tab it was in before, instead of spawning a ninth window. The name comes from that: each server perches in its own spot and returns to it.

It has since grown a few larger conveniences: a favorites set you launch as a group, optional desktop placement and tiling across multiple monitors (via yabai), and a small web dashboard with a spatial arranger you can drag windows around in.

## Features

- Launch a registered project by name alone: `perch acme-api`.
- One reusable tab per server, matched by tab title. No window pileup.
- Frees the port before starting, so restarts never die with `EADDRINUSE`.
- Servers outlive the shell that launched them. They run in real Terminal tabs, not child processes.
- **Favorites**: pick a working set once, launch it all with `perch fav go`, stop it with `perch killall`.
- **Desktop placement (optional)**: send each server to a specific desktop by category, tiled full width and stacked, across any monitor layout. Off cleanly if you don't want it.
- **Window position memory**: a closed-and-reopened server returns to its last size, position, and monitor.
- **Web dashboard**: `perch gui` opens a local dashboard with live status, one-click start/stop, and a spatial arranger where you drag terminals between desktops and save.
- **Portable**: `perch setup` auto-detects the machine's monitors and writes a sensible layout; `perch doctor` tells you exactly what (if anything) to install.

The "outlive the shell" point is the reason this exists as more than an alias. I use coding agents heavily, and a server started from an agent's shell dies when the session ends. A server started through perch does not.

## Install

```bash
git clone https://github.com/Jaybee4real/perch.git
cd perch
./install.sh
perch doctor          # tells you if anything optional is missing
```

The installer symlinks `perch` into `~/.local/bin` and seeds `~/.config/perch/projects.conf` with a sample registry, unless you already have one, in which case it leaves yours alone. It keeps a `pz-dev` symlink around too, because that was the tool's old name.

macOS only. It drives Terminal.app through AppleScript, so iTerm2 and other emulators are out. Desktop placement and the dashboard are optional and degrade gracefully if their dependencies are absent (see Requirements).

## Quickstart

Say you work on a product called Acme, with a web app, an API, and a mobile app:

```bash
perch add acme-web 3000 ~/code/acme/web "yarn dev"
perch add acme-api 8000 ~/code/acme/api "yarn start:dev"
perch add acme-metro 8082 ~/code/acme/mobile "yarn start"

perch acme-api          # API starts in a tab titled acme-api
perch acme-api          # later: same tab, port freed, server restarted in place
perch stop acme-web     # kill whatever is on 3000
```

The ad-hoc form still works for anything unregistered. Pass `-` as the port for tools that do not hold one:

```bash
perch scratch-tool ~/code/scratch 5000 "npm run dev"
```

## Commands

```
perch <project>                 launch a registered project (restart in place if already open)
perch <marker> <dir> <port> <cmd>   ad-hoc launch of anything

perch fav                       interactive picker: choose a working set, save + launch
perch fav go                    launch the saved favorites (no menu)
perch fav set|add|list|clear    manage the favorites list
perch pick                      alias for `perch fav`

perch place [fav]               move open windows to their desktops + tile full-width, stacked
perch place [fav] notile        move to desktops but leave windows free-floating
perch killall [--close] [fav]   stop running servers (optionally close their tabs; optionally just favorites)
perch stop <project|port>       free one port

perch gui                       open the web dashboard (http://localhost:7620)
perch gui stop                  stop the dashboard server

perch set                       show optional settings (placement, tile)
perch set placement <on|off>    toggle desktop placement
perch set tile <on|off>         toggle full-width stacked tiling

perch setup                     auto-detect this machine's monitors + write the desktop map
perch doctor                    check dependencies and config, with copy-paste fixes

perch list                      every project, its port, whether it's up
perch add / remove              register / unregister a project
perch bounds [clear [name]]     inspect / forget remembered window positions
perch config | help | -v
```

## Favorites

Most days I want the same dozen-ish servers up. Register everything once, then pick the set:

```bash
perch fav          # a grouped picker; type numbers, ranges (1-5), a group name (metro, web, ...), then Enter
perch fav go       # brings them all up in category order: Metro, Landing, Web, Backend, Admin
perch killall fav  # stops just the favorites
```

Selections persist in `~/.config/perch/favorites`. `perch fav set a b c` writes the set non-interactively.

## Desktop placement and tiling (optional)

If [yabai](https://github.com/koekeishiya/yabai) is installed and running, perch can send each server to a specific desktop and tile the windows there full width, stacked one after another. Categories are inferred from the project name and port (metro, landing, web, backend, admin), and each category maps to a desktop.

```bash
perch setup        # detect monitors, write ~/.config/perch/spaces.conf for THIS machine
perch fav go       # launches + places + tiles
perch place        # re-apply placement to whatever is open (no restart)
```

macOS renumbers its Mission Control spaces whenever a fullscreen app appears, so the map is written as `display:desktop` (for example `metro|2:2` means "display 2, desktop 2, counting real desktops only") and resolved to a live index at placement time. Edit `~/.config/perch/spaces.conf` by hand, or just drag windows in the dashboard and save.

`perch setup` adapts to whatever you have: on a single-screen laptop everything lands on one desktop; with four or more desktops it reserves desktop 1 for your own work and spreads servers across 2, 3, 4. If there is no map yet, the first `perch place` writes one automatically.

Turn it all off with `perch set placement off`. Without yabai, placement is simply skipped and everything else works.

## The web dashboard

```bash
perch gui
```

Opens a local dashboard at `http://localhost:7620` (bound to localhost only). It shells out to the same CLI, so the two never drift. Two views:

- **Servers**: every project grouped by category with a live up/down dot, one-click start and stop, and a favorite toggle.
- **Layout**: a to-scale map of your monitors (position and orientation), each desktop drawn as a mini screen with every window in its real place. perch terminals are colored and draggable; other apps and fullscreen spaces are shown dimmed for context. Drag a terminal to another desktop, hit Save, and it moves the window, remembers the new desktop in `spaces.conf`, and re-tiles.

## Window position memory

Whether or not you use desktop placement, perch remembers each server's window rectangle and restores it when it has to open a fresh window (a reused tab is left alone). With yabai this covers the monitor and desktop too. Inspect or reset with `perch bounds`.

## The registry

`~/.config/perch/projects.conf`, one line per project:

```
name|port|dir|command
```

```
acme-web|3000|~/code/acme/web|yarn dev
acme-api|8000|~/code/acme/api|yarn start:dev
acme-desktop|-|~/code/acme/desktop|$HOME/tools/flutter/bin/flutter run
```

Lines starting with `#` are comments. `~` and `$HOME` both expand. Edit the file directly or use `perch add`.

One convention worth copying: bake each project's port into its own dev script (`vite --port 3011 --strictPort`, `next dev -p 3001`). perch frees the port before launching but cannot stop a server from binding somewhere else. Pinning the port in the script keeps the port column in `perch list` honest.

## Requirements

- **macOS** with Terminal.app. AppleScript is load-bearing; there is no Linux or Windows port.
- **python3** (ships with the Xcode command line tools) for the web dashboard and `perch setup`.
- **yabai** for desktop placement only. Install with `brew install koekeishiya/formulae/yabai`, run `yabai --start-service`, and grant it Accessibility. Everything except placement works without it.

Run `perch doctor` and it prints exactly which of these is missing plus the command to fix it.

## How the tab reuse works

AppleScript walks every Terminal window and compares each tab's custom title against the project name. On a match, the command runs in that tab and the window comes forward. No match, one new tab, titled. Some Terminal windows (the Settings window, for one) do not expose tabs and throw if you ask, so the loop wraps each window in a `try`. That guard looks paranoid but its absence produced error -1728 often enough that I learned to keep it.

Killing the old server is a plain `lsof -ti tcp:<port> | xargs kill -9`. Blunt, but for dev servers I have never wanted the graceful version, I want the port back. `perch killall --close` is gentler about the tab: it kills each window's whole tty group first so Terminal does not pop its "terminate running processes?" prompt.

## Things it does not do

- No Linux, no Windows. AppleScript is load-bearing.
- It will not stop you from registering two projects on the same port. `perch list` makes the clash easy to spot.
- Rename a project and its old tab keeps the old title and gets orphaned. Close it yourself.
- Desktop placement cannot create Mission Control desktops for you. Make them in Mission Control first; `perch setup` maps to whatever exists.
