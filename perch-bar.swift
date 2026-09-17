import SwiftUI
import AppKit
import Darwin

struct Project: Identifiable, Equatable {
    let name: String
    let port: String
    let cat: String
    let up: Bool
    var park: Bool = true
    var id: String { name }
}

struct CatGroup: Identifiable {
    let cat: String
    let items: [Project]
    var id: String { cat }
}

struct PinnedApp: Identifiable, Equatable {
    let name: String
    let spec: String
    let park: Bool       // true = parked on disconnect; false = exempt (stays in place)
    var id: String { name }
}

func appIconImage(_ name: String) -> NSImage? {
    if let running = NSWorkspace.shared.runningApplications.first(where: { $0.localizedName == name }),
       let icon = running.icon { return icon }
    let fm = FileManager.default
    for base in ["/Applications", "/System/Applications", NSHomeDirectory() + "/Applications"] {
        let path = base + "/" + name + ".app"
        if fm.fileExists(atPath: path) { return NSWorkspace.shared.icon(forFile: path) }
    }
    return nil
}

struct Agent: Identifiable, Equatable {
    let name: String
    let status: String   // working | blocked | idle
    let dir: String
    var id: String { name }
    var color: Color {
        switch status {
        case "working": return .green
        case "blocked": return .red
        default:        return .secondary
        }
    }
}

final class PerchModel: ObservableObject {
    @Published var projects: [Project] = []
    @Published var agents: [Agent] = []
    @Published var pinnedApps: [PinnedApp] = []
    @Published var parkOn = true
    @Published var downText = "0"
    @Published var upText = "0"
    @Published var totalDown = "0 B"
    @Published var totalUp = "0 B"
    private var startRx: UInt64 = 0
    private var startTx: UInt64 = 0
    private var lastRx: UInt64 = 0
    private var lastTx: UInt64 = 0
    private var lastSample = Date()
    private var netTimer: Timer?
    @Published var downHistory: [Double] = []
    @Published var upHistory: [Double] = []
    @Published var latencyHistory: [Double] = []
    @Published var latencyText = "—"
    private var latencyTimer: Timer?
    private let perch = FileManager.default.homeDirectoryForCurrentUser.path + "/.local/bin/perch"
    private let catOrder = ["metro", "landing", "web", "backend", "admin", "other"]
    private var timer: Timer?

    init() {
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 4, repeats: true) { [weak self] _ in self?.refresh() }
        let start = Self.netBytes(); lastRx = start.rx; lastTx = start.tx; startRx = start.rx; startTx = start.tx
        netTimer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { [weak self] _ in self?.sampleNet() }
        measureLatency()
        latencyTimer = Timer.scheduledTimer(withTimeInterval: 2.5, repeats: true) { [weak self] _ in self?.measureLatency() }
    }

    static func netBytes() -> (rx: UInt64, tx: UInt64) {
        var rx: UInt64 = 0, tx: UInt64 = 0
        var head: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&head) == 0, head != nil else { return (0, 0) }
        defer { freeifaddrs(head) }
        var ptr = head
        while let cur = ptr {
            defer { ptr = cur.pointee.ifa_next }
            let name = String(cString: cur.pointee.ifa_name)
            guard cur.pointee.ifa_addr?.pointee.sa_family == UInt8(AF_LINK) else { continue }
            if name == "lo0" || name.hasPrefix("utun") || name.hasPrefix("awdl") || name.hasPrefix("bridge") || name.hasPrefix("llw") { continue }
            if let raw = cur.pointee.ifa_data {
                let data = raw.assumingMemoryBound(to: if_data.self).pointee
                rx += UInt64(data.ifi_ibytes)
                tx += UInt64(data.ifi_obytes)
            }
        }
        return (rx, tx)
    }

    static func rate(_ bytesPerSec: Double) -> String {
        if bytesPerSec >= 1_000_000 { return String(format: "%.1fM", bytesPerSec / 1_000_000) }
        if bytesPerSec >= 1_000 { return String(format: "%.0fK", bytesPerSec / 1_000) }
        return "0"
    }

    static func bytes(_ n: UInt64) -> String {
        let d = Double(n)
        if d >= 1_000_000_000 { return String(format: "%.2f GB", d / 1_000_000_000) }
        if d >= 1_000_000 { return String(format: "%.1f MB", d / 1_000_000) }
        if d >= 1_000 { return String(format: "%.0f KB", d / 1_000) }
        return "\(n) B"
    }

    func sampleNet() {
        let now = Date()
        let elapsed = max(now.timeIntervalSince(lastSample), 0.1)
        let cur = Self.netBytes()
        let dRx = cur.rx >= lastRx ? Double(cur.rx - lastRx) : 0
        let dTx = cur.tx >= lastTx ? Double(cur.tx - lastTx) : 0
        lastRx = cur.rx; lastTx = cur.tx; lastSample = now
        let d = Self.rate(dRx / elapsed)
        let u = Self.rate(dTx / elapsed)
        downHistory.append(dRx / elapsed); if downHistory.count > 40 { downHistory.removeFirst() }
        upHistory.append(dTx / elapsed); if upHistory.count > 40 { upHistory.removeFirst() }
        if d != downText { downText = d }
        if u != upText { upText = u }
        let sd = Self.bytes(lastRx >= startRx ? lastRx - startRx : 0)
        let su = Self.bytes(lastTx >= startTx ? lastTx - startTx : 0)
        if sd != totalDown { totalDown = sd }
        if su != totalUp { totalUp = su }
    }

    func measureLatency() {
        DispatchQueue.global(qos: .utility).async { [weak self] in
            let proc = Process()
            proc.executableURL = URL(fileURLWithPath: "/sbin/ping")
            proc.arguments = ["-c", "1", "-W", "1000", "1.1.1.1"]
            let pipe = Pipe(); proc.standardOutput = pipe; proc.standardError = FileHandle.nullDevice
            do { try proc.run() } catch { return }
            let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            proc.waitUntilExit()
            var ms = -1.0
            if let r = out.range(of: "time=") {
                let rest = out[r.upperBound...]
                if let sp = rest.firstIndex(of: " ") { ms = Double(rest[..<sp]) ?? -1 }
            }
            DispatchQueue.main.async {
                guard let self else { return }
                if ms >= 0 {
                    self.latencyText = String(format: "%.0f ms", ms)
                    self.latencyHistory.append(ms)
                    if self.latencyHistory.count > 40 { self.latencyHistory.removeFirst() }
                } else { self.latencyText = "—" }
            }
        }
    }

    var running: [Project] { projects.filter { $0.up } }
    var blockedAgents: Int { agents.filter { $0.status == "blocked" }.count }

    var barText: String {
        let count = running.count
        let prefix = count > 0 ? "\(count)  " : ""
        let warn = blockedAgents > 0 ? "⚠\(blockedAgents)  " : ""
        return warn + prefix + "↓\(downText) ↑\(upText)"
    }

    var grouped: [CatGroup] {
        var byCat: [String: [Project]] = [:]
        for project in projects { byCat[project.cat, default: []].append(project) }
        return byCat.keys
            .sorted { (catOrder.firstIndex(of: $0) ?? 99) < (catOrder.firstIndex(of: $1) ?? 99) }
            .map { CatGroup(cat: $0, items: byCat[$0] ?? []) }
    }

    private func process(_ args: [String]) -> Process {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: perch)
        proc.arguments = args
        var env = ProcessInfo.processInfo.environment
        env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + (env["PATH"] ?? "")
        proc.environment = env
        return proc
    }

    private func capture(_ args: [String]) -> String {
        let proc = process(args)
        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = FileHandle.nullDevice
        do { try proc.run() } catch { return "" }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        proc.waitUntilExit()
        return String(data: data, encoding: .utf8) ?? ""
    }

    private func fire(_ args: [String]) {
        let proc = process(args)
        proc.standardOutput = FileHandle.nullDevice
        proc.standardError = FileHandle.nullDevice
        try? proc.run()
    }

    func refresh() {
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self else { return }
            let list = self.capture(["list", "--plain"])
            let park = self.capture(["set", "park"]).trimmingCharacters(in: .whitespacesAndNewlines)
            let agentList = self.capture(["agents", "--plain"])
            let appList = self.capture(["apps", "--plain"])
            let parsed: [Project] = list.split(separator: "\n").compactMap { line in
                let fields = line.split(separator: "\t", omittingEmptySubsequences: false).map(String.init)
                guard fields.count >= 4 else { return nil }
                return Project(name: fields[0], port: fields[1], cat: fields[3], up: fields[2] == "up", park: fields.count >= 5 ? fields[4] != "off" : true)
            }
            let parsedAgents: [Agent] = agentList.split(separator: "\n").compactMap { line in
                let fields = line.split(separator: "\t", omittingEmptySubsequences: false).map(String.init)
                guard fields.count >= 2 else { return nil }
                return Agent(name: fields[0], status: fields[1], dir: fields.count >= 3 ? fields[2] : "")
            }
            let parsedApps: [PinnedApp] = appList.split(separator: "\n").compactMap { line in
                let fields = line.split(separator: "\t", omittingEmptySubsequences: false).map(String.init)
                guard fields.count >= 3 else { return nil }
                return PinnedApp(name: fields[0], spec: fields[1], park: fields[2] != "off")
            }
            DispatchQueue.main.async {
                if parsed != self.projects { self.projects = parsed }
                if parsedAgents != self.agents { self.agents = parsedAgents }
                if parsedApps != self.pinnedApps { self.pinnedApps = parsedApps }
                let on = park != "off"
                if on != self.parkOn { self.parkOn = on }
            }
        }
    }

    func setPark(_ on: Bool) {
        parkOn = on
        fire(["set", "park", on ? "on" : "off"])
    }

    func setAppPark(_ app: String, _ on: Bool) {
        if let idx = pinnedApps.firstIndex(where: { $0.name == app }) {
            let existing = pinnedApps[idx]
            pinnedApps[idx] = PinnedApp(name: existing.name, spec: existing.spec, park: on)
        }
        fire(["apps", "park", app, on ? "on" : "off"])
    }

    func setProjectPark(_ name: String, _ on: Bool) {
        if let idx = projects.firstIndex(where: { $0.name == name }) {
            var updated = projects[idx]
            updated.park = on
            projects[idx] = updated
        }
        fire(["apps", "park", name, on ? "on" : "off"])
    }

    func act(_ args: [String]) {
        fire(args)
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in self?.refresh() }
    }
}

struct HoverRow<Content: View>: View {
    let action: () -> Void
    let content: () -> Content
    @State private var hovering = false

    init(action: @escaping () -> Void, @ViewBuilder content: @escaping () -> Content) {
        self.action = action
        self.content = content
    }

    var body: some View {
        Button(action: action) {
            content()
                .frame(maxWidth: .infinity, alignment: .leading)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.primary.opacity(hovering ? 0.08 : 0)))
        .onHover { hovering = $0 }
    }
}

struct IconButton: View {
    let symbol: String
    let tip: String
    let action: () -> Void
    @State private var hovering = false

    var body: some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 11.5, weight: .semibold))
                .frame(width: 26, height: 22)
        }
        .buttonStyle(.plain)
        .background(RoundedRectangle(cornerRadius: 6).fill(Color.primary.opacity(hovering ? 0.14 : 0.06)))
        .onHover { hovering = $0 }
        .help(tip)
    }
}

struct Sparkline: View {
    let values: [Double]
    let color: Color
    var filled: Bool = false
    var maxValue: Double = 1

    var body: some View {
        GeometryReader { geo in
            let maxV = max(maxValue, 1)
            let n = max(values.count - 1, 1)
            let pts: [CGPoint] = values.enumerated().map { idx, v in
                CGPoint(x: geo.size.width * CGFloat(idx) / CGFloat(n),
                        y: geo.size.height * (1 - CGFloat(min(v / maxV, 1))) )
            }
            if pts.count > 1 {
                if filled {
                    Path { path in
                        path.move(to: CGPoint(x: pts.first!.x, y: geo.size.height))
                        for pt in pts { path.addLine(to: pt) }
                        path.addLine(to: CGPoint(x: pts.last!.x, y: geo.size.height))
                        path.closeSubpath()
                    }
                    .fill(LinearGradient(colors: [color.opacity(0.30), color.opacity(0.02)], startPoint: .top, endPoint: .bottom))
                }
                Path { path in
                    path.move(to: pts.first!)
                    for pt in pts.dropFirst() { path.addLine(to: pt) }
                }
                .stroke(color, style: StrokeStyle(lineWidth: 1.6, lineJoin: .round))
            }
        }
    }
}

struct PerchPanel: View {
    @EnvironmentObject var model: PerchModel
    @State private var showAll = false
    @State private var showParkTerms = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            divider
            networkCard
            divider
            runningSection
            divider
            agentsSection
            divider
            startSection
            divider
            parkToggle
            divider
            footer
        }
        .padding(14)
        .frame(width: 344)
        .onAppear { model.refresh() }
    }

    var divider: some View { Divider().padding(.vertical, 9) }

    var header: some View {
        HStack(spacing: 8) {
            Image(systemName: "bird.fill").font(.title3).foregroundStyle(.tint)
            Text("perch").font(.system(size: 15, weight: .bold))
            Spacer()
            Text(model.running.isEmpty ? "idle" : "\(model.running.count) running")
                .font(.caption.weight(.semibold))
                .padding(.horizontal, 9).padding(.vertical, 3)
                .background(Capsule().fill(model.running.isEmpty ? Color.secondary.opacity(0.15) : Color.green.opacity(0.18)))
                .foregroundStyle(model.running.isEmpty ? Color.secondary : Color.green)
        }
    }

    func sectionTitle(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 10.5, weight: .bold))
            .foregroundStyle(.secondary)
            .tracking(0.7)
            .padding(.horizontal, 10)
            .padding(.bottom, 3)
    }

    var netScale: Double { max((model.downHistory + model.upHistory).max() ?? 1, 1) }
    var latencyColor: Color {
        guard let last = model.latencyHistory.last else { return .secondary }
        return last < 60 ? .green : (last < 150 ? .orange : .red)
    }

    var networkCard: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack {
                Text("NETWORK").font(.system(size: 10.5, weight: .bold)).foregroundStyle(.secondary).tracking(0.7)
                Spacer()
                HStack(spacing: 4) {
                    Image(systemName: "dot.radiowaves.left.and.right").font(.system(size: 10, weight: .semibold)).foregroundStyle(latencyColor)
                    Text(model.latencyText).font(.system(size: 11, weight: .semibold).monospacedDigit()).foregroundStyle(latencyColor)
                }
            }
            ZStack {
                Sparkline(values: model.downHistory, color: .blue, filled: true, maxValue: netScale)
                Sparkline(values: model.upHistory, color: .green, filled: false, maxValue: netScale)
                if model.downHistory.count < 2 {
                    Text("sampling…").font(.system(size: 10)).foregroundStyle(.secondary)
                }
            }
            .frame(height: 46)
            .padding(7)
            .background(RoundedRectangle(cornerRadius: 9).fill(Color.primary.opacity(0.045)))
            HStack(spacing: 0) {
                netStat(symbol: "arrow.down", color: .blue, rate: model.downText, total: model.totalDown)
                Rectangle().fill(Color.primary.opacity(0.09)).frame(width: 1, height: 30)
                netStat(symbol: "arrow.up", color: .green, rate: model.upText, total: model.totalUp)
            }
        }
    }

    func netStat(symbol: String, color: Color, rate: String, total: String) -> some View {
        VStack(spacing: 2) {
            HStack(spacing: 5) {
                Image(systemName: symbol).font(.system(size: 11, weight: .bold)).foregroundStyle(color)
                Text(rate + "/s").font(.system(size: 15, weight: .semibold).monospacedDigit())
            }
            Text(total + " total").font(.system(size: 10)).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    var runningSection: some View {
        VStack(alignment: .leading, spacing: 3) {
            sectionTitle("RUNNING")
            if model.running.isEmpty {
                Text("No servers running")
                    .font(.callout).foregroundStyle(.secondary)
                    .padding(.horizontal, 10).padding(.vertical, 6)
            } else {
                ForEach(model.running) { project in
                    HStack(spacing: 10) {
                        Circle().fill(Color.green).frame(width: 8, height: 8)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(project.name).font(.system(size: 13, weight: .semibold))
                            Text("\(project.port)  ·  \(project.cat)").font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        IconButton(symbol: "arrow.clockwise", tip: "Restart in its tab") { model.act([project.name]) }
                        IconButton(symbol: "safari", tip: "Open in browser") { model.act(["open", project.name]) }
                        IconButton(symbol: "stop.fill", tip: "Stop") { model.act(["stop", project.name]) }
                    }
                    .padding(.horizontal, 10).padding(.vertical, 7)
                    .background(RoundedRectangle(cornerRadius: 9).fill(Color.primary.opacity(0.045)))
                }
            }
        }
    }

    var agentsSection: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                sectionTitle("AGENTS")
                Spacer()
                if model.blockedAgents > 0 {
                    Text("\(model.blockedAgents) blocked")
                        .font(.system(size: 10, weight: .bold))
                        .padding(.horizontal, 7).padding(.vertical, 2)
                        .background(Capsule().fill(Color.red.opacity(0.18)))
                        .foregroundStyle(.red)
                        .padding(.trailing, 10)
                }
            }
            if model.agents.isEmpty {
                Text("No agents running")
                    .font(.callout).foregroundStyle(.secondary)
                    .padding(.horizontal, 10).padding(.vertical, 6)
            } else {
                ForEach(model.agents) { agent in
                    HStack(spacing: 10) {
                        Circle().fill(agent.color).frame(width: 8, height: 8)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(agent.name).font(.system(size: 13, weight: .semibold))
                            Text(agent.status).font(.caption).foregroundStyle(agent.status == "blocked" ? .red : .secondary)
                        }
                        Spacer()
                        IconButton(symbol: "rectangle.stack", tip: "Open cockpit (all agents in one terminal)") { model.act(["cockpit"]) }
                        IconButton(symbol: "arrow.clockwise", tip: "Restart this agent") { model.act(["agent", "restart", agent.name]) }
                        IconButton(symbol: "stop.fill", tip: "Stop") { model.act(["agent", "stop", agent.name]) }
                    }
                    .padding(.horizontal, 10).padding(.vertical, 7)
                    .background(RoundedRectangle(cornerRadius: 9).fill(agent.status == "blocked" ? Color.red.opacity(0.08) : Color.primary.opacity(0.045)))
                }
                HoverRow(action: { model.act(["cockpit"]) }) {
                    HStack(spacing: 8) {
                        Image(systemName: "rectangle.stack").foregroundStyle(.tint)
                        Text("Open cockpit").font(.system(size: 12.5, weight: .medium))
                        Spacer()
                        Text("all agents · one terminal").font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    var startSection: some View {
        VStack(alignment: .leading, spacing: 2) {
            HoverRow(action: { withAnimation(.easeInOut(duration: 0.15)) { showAll.toggle() } }) {
                HStack {
                    Image(systemName: "play.circle").foregroundStyle(.secondary)
                    Text("Start a project").font(.system(size: 13, weight: .medium))
                    Spacer()
                    Text("\(model.projects.count)").font(.caption).foregroundStyle(.secondary)
                    Image(systemName: showAll ? "chevron.up" : "chevron.down").font(.caption).foregroundStyle(.secondary)
                }
            }
            if showAll {
                ScrollView {
                    VStack(alignment: .leading, spacing: 2) {
                        ForEach(model.grouped) { group in
                            sectionTitle(group.cat.uppercased()).padding(.top, 6)
                            ForEach(group.items) { project in
                                HoverRow(action: { model.act([project.name]) }) {
                                    HStack(spacing: 10) {
                                        Circle().fill(project.up ? Color.green : Color.secondary.opacity(0.35)).frame(width: 7, height: 7)
                                        Text(project.name).font(.system(size: 12.5))
                                        Spacer()
                                        if project.port != "-" {
                                            Text(project.port).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                .frame(maxHeight: 280)
            }
        }
    }

    var parkToggle: some View {
        VStack(alignment: .leading, spacing: 4) {
            Toggle(isOn: Binding(get: { model.parkOn }, set: { model.setPark($0) })) {
                VStack(alignment: .leading, spacing: 1) {
                    Text("Park windows when a monitor unplugs").font(.system(size: 12.5, weight: .medium))
                    Text("Hides any managed window — terminals and pinned apps — that gets dumped onto the laptop screen, and restores it on reconnect.")
                        .font(.caption).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .toggleStyle(.switch)
            .controlSize(.small)
            Button { model.act(["gui"]) } label: {
                Label("See how windows are organized", systemImage: "rectangle.3.group")
                    .font(.caption.weight(.medium))
            }
            .buttonStyle(.plain)
            .foregroundStyle(.tint)

            parkExemptions
        }
        .padding(.horizontal, 10)
    }

    var parkExemptions: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("KEEP IN PLACE — turn one off so it isn't parked")
                .font(.system(size: 9.5, weight: .bold)).foregroundStyle(.secondary).tracking(0.4)
                .padding(.top, 8)

            if !model.pinnedApps.isEmpty {
                ForEach(model.pinnedApps) { app in
                    exemptRow(name: app.name,
                              subtitle: "app · display \(app.spec)",
                              nsIcon: appIconImage(app.name),
                              symbol: "app.dashed",
                              isParked: app.park) { model.setAppPark(app.name, $0) }
                }
            }

            HoverRow(action: { withAnimation(.easeInOut(duration: 0.15)) { showParkTerms.toggle() } }) {
                HStack(spacing: 8) {
                    Image(systemName: "terminal.fill").font(.system(size: 12)).foregroundStyle(.secondary)
                    Text("Terminals").font(.system(size: 12.5, weight: .medium))
                    Spacer()
                    Text("\(model.running.count)").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                    Image(systemName: showParkTerms ? "chevron.up" : "chevron.down").font(.caption).foregroundStyle(.secondary)
                }
            }
            if showParkTerms {
                if model.running.isEmpty {
                    Text("No open terminals to de-pin")
                        .font(.caption).foregroundStyle(.secondary)
                        .padding(.horizontal, 10).padding(.vertical, 4)
                } else {
                    ForEach(model.running) { proj in
                        exemptRow(name: proj.name,
                                  subtitle: "terminal · \(proj.cat)",
                                  nsIcon: nil,
                                  symbol: "terminal.fill",
                                  isParked: proj.park) { model.setProjectPark(proj.name, $0) }
                    }
                }
            }
        }
    }

    func exemptRow(name: String, subtitle: String, nsIcon: NSImage?, symbol: String,
                   isParked: Bool, toggle: @escaping (Bool) -> Void) -> some View {
        HStack(spacing: 9) {
            Group {
                if let icon = nsIcon { Image(nsImage: icon).resizable() }
                else { Image(systemName: symbol).resizable().scaledToFit().foregroundStyle(.secondary) }
            }
            .frame(width: 18, height: 18)
            VStack(alignment: .leading, spacing: 1) {
                Text(name).font(.system(size: 12.5, weight: .semibold)).lineLimit(1)
                Text(isParked ? subtitle : "stays in place on disconnect")
                    .font(.caption).foregroundStyle(isParked ? Color.secondary : Color.orange).lineLimit(1)
            }
            Spacer(minLength: 6)
            if !isParked {
                Image(systemName: "pin.fill").font(.system(size: 10)).foregroundStyle(.orange)
            }
            Toggle("", isOn: Binding(get: { isParked }, set: { on in toggle(on) }))
                .labelsHidden().toggleStyle(.switch).controlSize(.mini)
        }
        .padding(.horizontal, 10).padding(.vertical, 6)
        .background(RoundedRectangle(cornerRadius: 9).fill(isParked ? Color.primary.opacity(0.05) : Color.orange.opacity(0.12)))
        .overlay(RoundedRectangle(cornerRadius: 9).stroke(isParked ? Color.clear : Color.orange.opacity(0.35), lineWidth: 1))
    }

    var footer: some View {
        VStack(spacing: 6) {
            HStack(spacing: 6) {
                footButton("Place all", "rectangle.3.group", ["place"])
                footButton("Favorites", "star", ["fav", "go"])
            }
            HStack(spacing: 6) {
                footButton("Dashboard", "globe", ["gui"])
                footButton("Stop all", "xmark.octagon", ["killall"], destructive: true)
            }
            Button { NSApp.terminate(nil) } label: {
                Text("Quit PerchBar").font(.caption)
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
            .padding(.top, 3)
        }
    }

    func footButton(_ label: String, _ symbol: String, _ args: [String], destructive: Bool = false) -> some View {
        Button { model.act(args) } label: {
            Label(label, systemImage: symbol)
                .font(.caption.weight(.medium))
                .lineLimit(1)
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(.bordered)
        .controlSize(.small)
        .tint(destructive ? .red : .accentColor)
    }
}

@main
struct PerchBarApp: App {
    @StateObject private var model = PerchModel()

    var body: some Scene {
        MenuBarExtra {
            PerchPanel().environmentObject(model)
        } label: {
            HStack(spacing: 3) {
                Image(systemName: "bird.fill")
                Text(model.barText)
                    .font(.system(size: 11, weight: .medium).monospacedDigit())
            }
        }
        .menuBarExtraStyle(.window)
    }
}
