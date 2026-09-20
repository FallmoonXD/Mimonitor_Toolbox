import SwiftUI
import AppKit

/// 应用主题（对应工具页的「应用主题」选项）。
///
/// 用 `NSApp.appearance` 而不是 SwiftUI 的 `.preferredColorScheme`：
/// 前者作用于整个进程，AppKit 部分（悬浮窗那个 NSPanel、弹出菜单等）也跟着变；
/// 后者只影响被修饰的那棵 SwiftUI 视图树，面板会漏掉。
enum AppTheme {
    static let key = "theme"

    static var current: String {
        UserDefaults.standard.string(forKey: key) ?? "auto"
    }

    static func apply(_ name: String) {
        switch name {
        case "dark":  NSApp.appearance = NSAppearance(named: .darkAqua)
        case "light": NSApp.appearance = NSAppearance(named: .aqua)
        default:      NSApp.appearance = nil      // nil = 跟随系统
        }
    }

    static func applyCurrent() { apply(current) }
}

/// 窗口关闭行为（对应工具页里的「窗口关闭行为」选项，与原版一致）：
///   - tray：关掉窗口只是隐藏，应用继续驻留在菜单栏
///   - exit：关掉窗口直接退出
/// 由 Info.plist 的 LSUIElement 让应用不出现在 Dock，所以「隐藏窗口」不会顺带退出。
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        // 启动时先把主题应用上，否则会先闪一下系统外观再切换
        AppTheme.applyCurrent()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        UserDefaults.standard.string(forKey: "close_behavior") == "exit"
    }
}

@main
struct MimonitorToolboxApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var state = AppState()

    var body: some Scene {
        // 用 Window（单例）而不是 WindowGroup：这是单窗口工具，
        // 而且菜单栏的「显示主窗口」需要能按 id 精确唤回同一个窗口。
        Window("红米G Pro ToolBox", id: "main") {
            ContentView()
                .environmentObject(state)
                // 主页连接那一行是全局最宽的内容：
                // 「显示器 IP:」标签 + 输入框 + 四个按钮 + 间距 + 内边距，再加 220 的侧边栏，
                // 实测要 ~935pt。原来给 900 会把「开始连接」和「扫描内网」挤到一起。
                .frame(minWidth: 1020, minHeight: 660)
        }
        .windowResizability(.contentMinSize)
        .commands {
            // 去掉「显示 → 隐藏边栏」（以及对应的快捷键），
            // 折叠入口一并砍掉：折叠/展开时侧边栏会抽一下（SwiftUI NavigationSplitView
            // 在动画收尾时还会再重排一次），本工具也不需要折叠，索性不支持。
            CommandGroup(replacing: .sidebar) { }
        }

        // 菜单栏图标（顶栏状态栏）。应用是 LSUIElement，不在 Dock 常驻。
        // 用 .window 样式而不是默认的 .menu：菜单里放不了滑块，
        // 而数值型条目（背光、对比度…）按步长加加减减太难用。
        MenuBarExtra {
            MenuBarPanel()
                .environmentObject(state)
        } label: {
            // 用 display 符号而不是应用图标：菜单栏图标惯例是单色符号，
            // 彩色图标混在 Wi-Fi / 电池那排里会很突兀。
            Image(systemName: "display")
        }
        .menuBarExtraStyle(.window)
    }
}

/// 菜单栏下方面板。比系统菜单自由得多 —— 能放滑块、分组、任意布局。
private struct MenuBarPanel: View {
    @EnvironmentObject var state: AppState
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // 状态行
            HStack(spacing: 8) {
                Circle()
                    .fill(state.statusColor)
                    .frame(width: 8, height: 8)
                Text(state.statusText)
                    .font(.callout)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Spacer()
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)

            Divider()

            if state.menuBarItems.isEmpty {
                Text("还没有添加快捷项。\n去「菜单栏」页挑几个。")
                    .font(.callout)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 24)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        ForEach(state.menuBarItems, id: \.self) { id in
                            if let entry = MenuBarCatalog.entry(id) {
                                MenuBarPanelRow(entry: entry)
                            }
                        }
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, 12)
                }
                .frame(maxHeight: 420)
            }

            Divider()

            HStack(spacing: 8) {
                Button("显示主窗口") {
                    openWindow(id: "main")
                    NSApp.activate(ignoringOtherApps: true)
                }
                if state.isConnected {
                    Button("断开") { state.disconnectAdb() }
                } else {
                    Button("重连") { state.connect() }
                }
                Spacer()
                Button("退出") { NSApp.terminate(nil) }
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
        }
        .frame(width: 320)
    }
}

/// 面板里的单个快捷项。
private struct MenuBarPanelRow: View {
    @EnvironmentObject var state: AppState
    let entry: MenuBarEntry

    /// 滑块拖动中的本地值：松手才下发，避免拖动过程刷出一串 ADB 命令
    @State private var dragging: Int?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            switch entry.kind {
            case .options(let options):
                Text(entry.label).font(.callout).foregroundColor(.secondary)
                Picker("", selection: Binding(
                    get: { state.menuBarValue(for: entry.id) ?? -1 },
                    set: { state.applyMenuBarOption(entry.id, value: $0) }
                )) {
                    ForEach(options) { opt in
                        Text(opt.label).tag(opt.value)
                    }
                }
                .pickerStyle(.menu)
                .labelsHidden()
                .frame(maxWidth: .infinity, alignment: .leading)

            case .stepper(let lo, let hi, _):
                let current = state.menuBarValue(for: entry.id) ?? lo
                HStack {
                    Text(entry.label).font(.callout).foregroundColor(.secondary)
                    Spacer()
                    Text("\(dragging ?? current)")
                        .font(.callout.monospacedDigit())
                        .foregroundColor(.primary)
                }
                // 用自绘的 FastSlider 而不是系统 Slider：
                // 后者底层是 NSSlider，每次创建都要向 CoreUI 解析主题 rendition，
                // 正是之前画面页切页卡 1.6 秒的根因（见 README 性能那节）。
                FastSlider(
                    value: Binding(
                        get: { Double(dragging ?? current) },
                        set: { dragging = Int($0.rounded()) }
                    ),
                    range: Double(lo)...Double(hi),
                    step: 1
                ) { v in
                    // 松手才提交
                    state.setMenuBarItem(entry.id, to: Int(v))
                    dragging = nil
                }
            }
        }
        .disabled(!state.isConnected)
        .opacity(state.isConnected ? 1 : 0.5)
    }
}

// 注：曾经的菜单式渲染（MenuBarMenu / MenuBarEntryMenu）已删除 ——
// 改成 .window 样式的面板后它就没有调用方了。
