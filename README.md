# perch

Start and restart dev servers in named, reusable macOS Terminal tabs.

I run a lot of servers at once: a few Next.js apps, some NestJS backends, four or five Metro bundlers on any given day. The usual way of scripting Terminal from the command line (`osascript ... do script`) opens a brand new window every single time. Restart Metro eight times in an afternoon and you have eight dead windows and no idea which one is live.

perch fixes that one annoyance. Every server gets a tab with a stable title. Run the same command again and the server restarts in the same tab it was in before, instead of spawning a ninth window. The name comes from that: each server perches in its own spot and returns to it.

## What it does

- Kills whatever is holding the server's port, so the restart actually binds instead of failing with `EADDRINUSE`.
- Finds the Terminal tab whose title matches the project name and reuses it. Only when no such tab exists does it create one.
- Keeps a registry of your projects, so `perch acme-api` is all you type. Directory, port, and command live in a config file, not in your head.
- Survives your terminal session. The server runs in a real Terminal.app tab, not a child process of whatever shell launched it, so closing that shell (or the AI agent that called it) leaves the server alive.

That last point is the reason this exists as more than an alias. I use coding agents heavily, and a server started from an agent's shell dies when the session ends. A server started through perch doesn't.

## Install

```bash
git clone https://github.com/Jaybee4real/perch.git
cd perch
./install.sh
```

The installer symlinks `perch` into `~/.local/bin` and seeds `~/.config/perch/projects.conf` with the registry from the repo, unless you already have one, in which case it leaves yours alone. It also keeps a `pz-dev` symlink around because that was the tool's old name and I still type it sometimes.

macOS only. It drives Terminal.app through AppleScript, so iTerm2 and other emulators are out (for now).

## Usage

```bash
perch <project>                        # launch a registered project
perch list                             # every project, its port, and whether it's up
perch stop <project|port>              # free the port
perch add <name> <port> <dir> <cmd...> # register a project
perch remove <name>                    # unregister
perch config                           # where the config file lives
perch help
```

And the original ad-hoc form still works for anything unregistered:

```bash
perch my-tool ~/code/my-tool 5000 "npm run dev"
```

Pass `-` as the port for tools that don't hold one (a Flutter run, a watcher, a REPL).

## The registry

`~/.config/perch/projects.conf`, one line per project:

```
name|port|dir|command
```

```
acme-api|8000|~/code/acme/acme-api|yarn start:dev
acme-metro|8085|~/code/acme/acme-mobile|yarn start
tech-summit-app|-|~/code/Tech_Summit/tech_summit_app|$HOME/Tools/flutter/bin/flutter run
```

Lines starting with `#` are comments. `~` and `$HOME` both expand. Edit the file directly or use `perch add`; they do the same thing.

One convention worth copying: I bake each project's port into the project's own dev script (`vite --port 3011 --strictPort`, `next dev -p 3001`, and so on). perch frees the port before launching, but it can't stop a server from binding somewhere else. Pinning the port in the script means the port column in `perch list` is always telling the truth.

## How the tab reuse works

AppleScript walks every Terminal window and compares each tab's custom title against the project name. On a match, the command runs in that tab and the window comes forward. No match, one new tab, titled. Some Terminal windows (the Settings window, for one) don't expose tabs at all and throw if you ask, so the loop wraps each window in a `try`. That guard looks paranoid but its absence produced error -1728 often enough that I learned to keep it.

Killing the old server is a plain `lsof -ti tcp:<port> | xargs kill -9`. Blunt, yes. For dev servers I have never once wanted the graceful version, I want the port back.

## Things it doesn't do

- No Linux, no Windows. AppleScript is load-bearing.
- It won't stop you from registering two projects on the same port. The second one will just keep killing the first. The `list` output makes this easy to spot at least.
- If you rename a project, its old tab keeps the old title and gets orphaned. Close it yourself; perch only knows about titles it's told to look for.
