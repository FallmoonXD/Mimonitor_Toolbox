import SwiftUI

/// 配置菜单栏下拉里放哪些快捷项。
///
/// macOS 独有 —— Windows 原版那边是托盘图标，没有等价的自定义能力。
struct MenuBarSettingsView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("菜单栏").font(.title2.bold())
                    Text("选择要放进菜单栏下拉的快捷项，随时不开主窗口也能调")
                        .font(.callout).foregroundColor(.secondary)
                }

                // 当前顺序。用 List + onMove 提供真正的拖动排序 ——
                // 之前是普通 VStack 配了个拖动手柄图标，看着能拖其实拖不动。
                SectionCard(title: "已加入（\(state.menuBarItems.count)）") {
                    if state.menuBarItems.isEmpty {
                        Text("还没有添加任何快捷项。从下面挑几个吧。")
                            .foregroundColor(.secondary)
                    } else {
                        List {
                            ForEach(state.menuBarItems, id: \.self) { id in
                                if let entry = MenuBarCatalog.entry(id) {
                                    HStack(spacing: 10) {
                                        Text(entry.label)
                                        Spacer()
                                        Button { state.toggleMenuBarItem(id) } label: {
                                            Image(systemName: "minus.circle")
                                        }
                                        .buttonStyle(.borderless)
                                        .foregroundColor(.red)
                                    }
                                }
                            }
                            .onMove { from, to in state.moveMenuBarItems(from: from, to: to) }
                        }
                        .listStyle(.plain)
                        .scrollContentBackground(.hidden)
                        .environment(\.defaultMinListRowHeight, 28)
                        // List 自带滚动，嵌在外层 ScrollView 里必须给定高度
                        .frame(height: CGFloat(state.menuBarItems.count) * 28 + 6)
                    }
                }

                // 可选清单
                SectionCard(title: "可添加") {
                    ForEach(MenuBarCatalog.all) { entry in
                        HStack(spacing: 10) {
                            Image(systemName: icon(for: entry))
                                .frame(width: 18)
                                .foregroundColor(.secondary)
                            Text(entry.label)
                            Text(describe(entry))
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Spacer()
                            Toggle("", isOn: Binding(
                                get: { state.isMenuBarItemEnabled(entry.id) },
                                set: { _ in state.toggleMenuBarItem(entry.id) }
                            ))
                            .labelsHidden()
                            .toggleStyle(.switch)
                        }
                        .padding(.vertical, 2)
                    }
                }

                Text("提示：选项型条目在菜单里是打勾列表；数值型（背光、对比度等）给「增大 / 减小」两项 —— 菜单栏空间有限，不把 1~100 全铺开。")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(30)
        }
    }

    private func icon(for entry: MenuBarEntry) -> String {
        switch entry.kind {
        case .options: return "checklist"
        case .stepper: return "slider.horizontal.3"
        }
    }

    private func describe(_ entry: MenuBarEntry) -> String {
        switch entry.kind {
        case .options(let opts):
            let names = opts.map(\.label)
            return names.count <= 4
                ? "（\(names.joined(separator: " / "))）"
                : "（\(names.prefix(3).joined(separator: " / ")) 等 \(names.count) 项）"
        case .stepper(let lo, let hi, let step):
            return "（\(lo)~\(hi)，每次 \(step)）"
        }
    }
}
