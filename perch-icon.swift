import AppKit

let px = 1024
let out = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "icon.png"
guard let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: px, pixelsHigh: px,
      bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
      colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { exit(1) }
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let ctx = NSGraphicsContext.current!.cgContext
let f = CGFloat(px)
let inset: CGFloat = 84
let rect = CGRect(x: inset, y: inset, width: f - 2*inset, height: f - 2*inset)
let path = CGPath(roundedRect: rect, cornerWidth: 200, cornerHeight: 200, transform: nil)
let colors = [NSColor(calibratedRed: 0.20, green: 0.62, blue: 0.60, alpha: 1).cgColor,
              NSColor(calibratedRed: 0.06, green: 0.34, blue: 0.42, alpha: 1).cgColor] as CFArray
let grad = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 1])!
ctx.saveGState(); ctx.addPath(path); ctx.clip()
ctx.drawLinearGradient(grad, start: CGPoint(x: inset, y: f - inset), end: CGPoint(x: f - inset, y: inset), options: [])
ctx.restoreGState()
if let sym = NSImage(systemSymbolName: "bird.fill", accessibilityDescription: nil) {
    let conf = NSImage.SymbolConfiguration(pointSize: 520, weight: .semibold)
    let base = sym.withSymbolConfiguration(conf) ?? sym
    let tinted = NSImage(size: base.size)
    tinted.lockFocus()
    let r = NSRect(origin: .zero, size: base.size)
    base.draw(in: r)
    NSColor.white.set()
    r.fill(using: .sourceAtop)
    tinted.unlockFocus()
    let scale = min(f * 0.5 / tinted.size.width, f * 0.5 / tinted.size.height)
    let dw = tinted.size.width * scale, dh = tinted.size.height * scale
    tinted.draw(in: NSRect(x: (f - dw)/2, y: (f - dh)/2 - 10, width: dw, height: dh))
}
NSGraphicsContext.restoreGraphicsState()
guard let png = rep.representation(using: .png, properties: [:]) else { exit(1) }
try? png.write(to: URL(fileURLWithPath: out))
