import SwiftUI

struct RemoteView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("遥控器").font(.title2.bold())

            VStack(spacing: 18) {
                Text("G PRO CONTROL")
                    .font(.caption.bold())
                    .kerning(3)
                    .foregroundColor(Color(red: 0, green: 0.47, blue: 0.83))

                // 电源
                Button {
                    state.key("KEYCODE_POWER")
                } label: {
                    Image(systemName: "power")
                        .font(.title3)
                        .frame(width: 44, height: 44)
                        .background(Circle().fill(Color(red: 0.91, green: 0.07, blue: 0.14)))
                        .foregroundColor(.white)
                }
                .buttonStyle(.plain)

                // 主页 / 菜单 / 返回
                HStack(spacing: 10) {
                    remoteButton("主页") { state.key("KEYCODE_HOME") }
                    remoteButton("菜单") { state.key("KEYCODE_MENU") }
                    remoteButton("返回") { state.key("KEYCODE_BACK") }
                }

                // 方向键 + OK
                VStack(spacing: 4) {
                    HStack {
                        dpadButton("chevron.up") { state.key("KEYCODE_DPAD_UP") }
                    }
                    HStack(spacing: 4) {
                        dpadButton("chevron.left") { state.key("KEYCODE_DPAD_LEFT") }
                        Button {
                            state.key("KEYCODE_DPAD_CENTER")
                        } label: {
                            Text("OK").font(.subheadline.bold())
                                .frame(width: 62, height: 62)
                                .background(Circle().fill(Color.accentColor))
                                .foregroundColor(.white)
                        }
                        .buttonStyle(.plain)
                        dpadButton("chevron.right") { state.key("KEYCODE_DPAD_RIGHT") }
                    }
                    HStack {
                        dpadButton("chevron.down") { state.key("KEYCODE_DPAD_DOWN") }
                    }
                }
                .padding(14)
                .background(Circle().fill(Color.primary.opacity(0.06)))

                // 音量
                HStack(spacing: 8) {
                    remoteButton("🔉 音量-") { state.key("KEYCODE_VOLUME_DOWN") }
                    remoteButton("🔇 静音") { state.key("KEYCODE_VOLUME_MUTE") }
                    remoteButton("🔊 音量+") { state.key("KEYCODE_VOLUME_UP") }
                }
            }
            .frame(width: 300)
            .padding(24)
            .background(RoundedRectangle(cornerRadius: 16).fill(Theme.card))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.stroke))

            Spacer()
        }
        .padding(30)
    }

    private func remoteButton(_ title: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.callout)
                .frame(minWidth: 56)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Theme.control)
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
    }

    private func dpadButton(_ systemImage: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .font(.title3)
                .frame(width: 48, height: 44)
                .foregroundColor(.secondary)
        }
        .buttonStyle(.plain)
    }
}
