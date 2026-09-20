import Cocoa
import Carbon.HIToolbox
import ApplicationServices

// MARK: - 快捷键配置模型

struct HotkeyConfig: Codable, Equatable {
    var modifier: String = "无"
    var key: String = "无"
    var isEnabled: Bool { modifier != "无" && key != "无" }
}

struct AdjustHotkeyConfig: Codable, Equatable {
    var param: String = "backlight"
    var direction: String = "increase"
    var step: Int = 5
    var modifier: String = "无"
    var key: String = "无"
    var isEnabled: Bool { modifier != "无" && key != "无" }
}

enum HotkeyLists {
    /// 下拉里能选到的修饰键组合。名称必须和 `HotkeyMap.modifierName(for:)`
    /// 生成的一致，否则录入的快捷键在下拉里显示不出来。
    static let modifiers = [
        "无", "Cmd", "Cmd + Shift", "Cmd + Option", "Cmd + Ctrl",
        "Ctrl", "Ctrl + Alt", "Ctrl + Shift",
        "Alt", "Alt + Shift", "Shift",
    ]
}

/// 8 个循环切换动作（对应原版 tools 页 actions_list）
let hotkeyActions: [(id: String, label: String)] = [
    ("picture_mode_cycle", "画面模式 循环切换"),
    ("local_dimming_cycle", "精密控光 循环切换"),
    ("local_dimming_toggle_off", "精密控光 开关切换"),
    ("color_space_cycle", "色域 循环切换"),
    ("color_temp_cycle", "色温 循环切换"),
    ("response_time_cycle", "响应时间 循环切换"),
    ("freesync_toggle", "FreeSync 开关切换"),
    ("input_source_cycle", "信号源 循环切换"),
]

/// 可调参数（对应 core.py ADJUSTABLE_HOTKEY_PARAMS）
let adjustableParams: [(id: String, label: String, defaultStep: Int)] = [
    ("backlight", "背光", 5),
    ("black_level", "黑色级别", 5),
    ("contrast", "对比度", 5),
    ("saturation", "饱和度", 5),
    ("hue", "色调", 5),
    ("sharpness", "锐度", 1),
    ("red_gain", "红色增益", 10),
    ("green_gain", "绿色增益", 10),
    ("blue_gain", "蓝色增益", 10),
    ("atmosphere_illumination", "屏幕灯亮度", 1),
]

// MARK: - 按键 / 修饰键映射

enum HotkeyMap {
    static func modifiers(for name: String) -> CGEventFlags {
        var flags: CGEventFlags = []
        if name.contains("Cmd") || name.contains("Win") { flags.insert(.maskCommand) }
        if name.contains("Ctrl") { flags.insert(.maskControl) }
        if name.contains("Option") || name.contains("Alt") { flags.insert(.maskAlternate) }
        if name.contains("Shift") { flags.insert(.maskShift) }
        return flags
    }

    /// ANSI 按键码**不是按字母/数字顺序排列的** —— 字母按 QWERTY 物理位置排
    /// （A=0x00, D=0x02, C=0x08, B=0x0B…），数字也乱序
    /// （1=0x12, 2=0x13, 4=0x15, 6=0x16, 5=0x17, 9=0x19, 7=0x1A, 8=0x1C, 0=0x1D）。
    /// 早先这里用 `kVK_ANSI_A + 偏移` 硬算，导致所有字母/数字快捷键都匹配不上，
    /// 必须逐个列出来。
    private static let ansiTables: [String: Int] = [
        "A": kVK_ANSI_A, "B": kVK_ANSI_B, "C": kVK_ANSI_C, "D": kVK_ANSI_D,
        "E": kVK_ANSI_E, "F": kVK_ANSI_F, "G": kVK_ANSI_G, "H": kVK_ANSI_H,
        "I": kVK_ANSI_I, "J": kVK_ANSI_J, "K": kVK_ANSI_K, "L": kVK_ANSI_L,
        "M": kVK_ANSI_M, "N": kVK_ANSI_N, "O": kVK_ANSI_O, "P": kVK_ANSI_P,
        "Q": kVK_ANSI_Q, "R": kVK_ANSI_R, "S": kVK_ANSI_S, "T": kVK_ANSI_T,
        "U": kVK_ANSI_U, "V": kVK_ANSI_V, "W": kVK_ANSI_W, "X": kVK_ANSI_X,
        "Y": kVK_ANSI_Y, "Z": kVK_ANSI_Z,
        "0": kVK_ANSI_0, "1": kVK_ANSI_1, "2": kVK_ANSI_2, "3": kVK_ANSI_3,
        "4": kVK_ANSI_4, "5": kVK_ANSI_5, "6": kVK_ANSI_6, "7": kVK_ANSI_7,
        "8": kVK_ANSI_8, "9": kVK_ANSI_9,
    ]

    /// keyCode -> 显示名（`keyCode(for:)` 的反向）
    private static let reverseTable: [Int: String] = {
        var m: [Int: String] = [:]
        for (name, code) in ansiTables { m[code] = name }
        m[kVK_ANSI_Equal] = "+"
        m[kVK_ANSI_Minus] = "-"
        m[kVK_PageUp] = "PageUp"
        m[kVK_PageDown] = "PageDown"
        m[kVK_UpArrow] = "↑"
        m[kVK_DownArrow] = "↓"
        m[kVK_LeftArrow] = "←"
        m[kVK_RightArrow] = "→"
        for n in 1...12 { m[Int(kVK_F1) + n - 1] = "F\(n)" }
        return m
    }()

    /// 由按键事件反查显示名。录制快捷键时用。
    static func keyName(for code: CGKeyCode) -> String? {
        reverseTable[Int(code)]
    }

    /// 由修饰键标志生成名称。**顺序必须和 HotkeyLists.modifiers 里的写法一致**，
    /// 否则录制出来的值在下拉里匹配不上。
    static func modifierName(for flags: NSEvent.ModifierFlags) -> String {
        var parts: [String] = []
        if flags.contains(.command) { parts.append("Cmd") }
        if flags.contains(.control) { parts.append("Ctrl") }
        if flags.contains(.option) { parts.append("Alt") }
        if flags.contains(.shift) { parts.append("Shift") }
        return parts.isEmpty ? "无" : parts.joined(separator: " + ")
    }

    static func keyCode(for name: String) -> CGKeyCode? {
        if name == "无" || name.isEmpty { return nil }
        if let code = ansiTables[name.uppercased()] { return CGKeyCode(code) }
        if name == "+" { return CGKeyCode(kVK_ANSI_Equal) }
        if name == "-" { return CGKeyCode(kVK_ANSI_Minus) }
        if name.hasPrefix("F"), let n = Int(name.dropFirst()), n >= 1, n <= 12 {
            return CGKeyCode(kVK_F1) + UInt16(n - 1)
        }
        switch name {
        case "PageUp": return CGKeyCode(kVK_PageUp)
        case "PageDown": return CGKeyCode(kVK_PageDown)
        case "↑": return CGKeyCode(kVK_UpArrow)
        case "↓": return CGKeyCode(kVK_DownArrow)
        case "←": return CGKeyCode(kVK_LeftArrow)
        case "→": return CGKeyCode(kVK_RightArrow)
        default: return nil
        }
    }
}

// MARK: - 全局快捷键监听（CGEventTap）

final class HotkeyManager {
    struct Binding {
        let id: String
        let modifiers: CGEventFlags
        let keyCode: CGKeyCode
    }

    private var bindings: [Binding] = []
    private var eventTap: CFMachPort?
    private var runLoopSource: CFRunLoopSource?

    /// 触发回调：参数为绑定 id（cycle 用 action 名，adjust 用 "adjust:<index>"）。
    var onTrigger: ((String) -> Void)?

    /// 诊断用：按键码命中某条绑定但修饰键不匹配时回调。
    /// 用来区分「事件根本没到」和「到了但组合不对」。
    var onKeyCodeMatch: ((CGKeyCode, CGEventFlags, CGEventFlags) -> Void)?

    /// 诊断用：收到任意按键事件时回调
    var onKeyEvent: ((CGEvent) -> Void)?

    /// 监听被系统禁用时回调
    var onTapDisabled: (() -> Void)?

    private static let combinedMask: CGEventFlags = [.maskCommand, .maskControl, .maskAlternate, .maskShift]

    func register(id: String, modifierName: String, keyName: String) {
        bindings.removeAll { $0.id == id }
        guard modifierName != "无", keyName != "无",
              let keyCode = HotkeyMap.keyCode(for: keyName) else { return }
        bindings.append(Binding(id: id,
                                modifiers: HotkeyMap.modifiers(for: modifierName),
                                keyCode: keyCode))
    }

    func clear() { bindings.removeAll() }

    /// 返回是否成功建立了事件监听。
    /// `tapCreate` 在缺权限时会直接返回 nil —— 这种情况必须让调用方知道，
    /// 否则表现就是"快捷键配了但完全没反应"。
    @discardableResult
    func start() -> Bool {
        if eventTap != nil { return true }
        let mask = CGEventMask(1) << CGEventType.keyDown.rawValue
        let selfPtr = Unmanaged.passUnretained(self).toOpaque()
        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: mask,
            callback: { _, type, event, refcon in
                guard let refcon else { return Unmanaged.passUnretained(event) }
                let manager = Unmanaged<HotkeyManager>.fromOpaque(refcon).takeUnretainedValue()

                // 回调超时会被系统临时禁用。不重新启用的话快捷键就永久失效了，
                // 而且表面上完全看不出来（tap 还在，只是收不到事件）。
                if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
                    if let tap = manager.eventTap { CGEvent.tapEnable(tap: tap, enable: true) }
                    manager.onTapDisabled?()
                    return Unmanaged.passUnretained(event)
                }

                if type == .keyDown {
                    manager.receivedKeyEvents += 1
                    manager.onKeyEvent?(event)
                    manager.handle(event)
                }
                return Unmanaged.passUnretained(event)
            },
            userInfo: selfPtr
        ) else { return false }

        eventTap = tap
        runLoopSource = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
        if let runLoopSource {
            CFRunLoopAddSource(CFRunLoopGetMain(), runLoopSource, .commonModes)
        }
        CGEvent.tapEnable(tap: tap, enable: true)
        return true
    }

    /// 已注册的绑定数量（用于诊断）
    var bindingCount: Int { bindings.count }

    func stop() {
        if let eventTap { CGEvent.tapEnable(tap: eventTap, enable: false) }
        if let runLoopSource {
            CFRunLoopRemoveSource(CFRunLoopGetMain(), runLoopSource, .commonModes)
            self.runLoopSource = nil
        }
        eventTap = nil
    }

    private func handle(_ event: CGEvent) {
        let keyCode = CGKeyCode(event.getIntegerValueField(.keyboardEventKeycode))
        let flags = event.flags.intersection(Self.combinedMask)
        for binding in bindings where binding.keyCode == keyCode {
            let expected = binding.modifiers.intersection(Self.combinedMask)
            if expected == flags {
                onTrigger?(binding.id)
                break
            } else {
                // 只在真的不符时报告，便于排查"配了没反应"
                onKeyCodeMatch?(keyCode, flags, expected)
            }
        }
    }

    /// 事件是否已到达监听（用于诊断）
    private(set) var receivedKeyEvents = 0

    // MARK: 权限

    static var isTrusted: Bool { AXIsProcessTrusted() }

    /// 弹出系统授权引导。
    ///
    /// 系统会弹一个「「App」想要控制此电脑」的框，带「打开系统设置」按钮。
    /// **每个 app 只会弹一次**，之后这个调用就静默无效了 —— 所以用户拒绝过之后
    /// 必须靠 `openAccessibilitySettings()` 引导。
    @discardableResult
    static func promptForAccessibility() -> Bool {
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        return AXIsProcessTrustedWithOptions(options)
    }

    /// 直接打开「系统设置 → 隐私与安全性 → 辅助功能」
    static func openAccessibilitySettings() {
        let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")!
        NSWorkspace.shared.open(url)
    }

    /// 兼容旧调用点
    static func requestAccessibility() {
        _ = promptForAccessibility()
    }
}
