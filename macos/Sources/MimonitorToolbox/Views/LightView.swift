import SwiftUI

struct LightView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                PageHeader(title: "屏幕灯") { state.forceRefreshPage("light") }

                ButtonGroupSection(title: "炫彩灯模式", options: OptionLists.lightMode,
                                   selectedValue: state.intValue("atmosphere_light_switcher_pm2", default: 4)) { v in
                    state.setLightMode(v)
                }

                // 亮度挡位：存储值是 0..14（raw），UI 显示 1..15
                SliderRow(title: "亮度挡位", range: 1...15,
                          externalValue: state.intValue("atmosphere_light_illumination", default: 9) + 1) { v in
                    state.setLightIllumination(v)
                }

                ButtonGroupSection(title: "照明色温", options: OptionLists.lightColorTemp,
                                   selectedValue: state.intValue("atmosphere_light_color_temp", default: 1)) { v in
                    state.setLightColorTemp(v)
                }

                ButtonGroupSection(title: "纯色颜色", options: OptionLists.lightColor,
                                   selectedValue: state.intValue("atmosphere_light_color_value", default: 0)) { v in
                    state.setLightColor(v)
                }
            }
            .padding(30)
        }
        .onAppear { state.refreshPage("light") }
    }
}
