# Desk charts are frappe-ui charts

Desk draws its charts with frappe-charts. frappe-ui ships a family of charts that apps built on it already use, and desk's copies of their colours drift from them. Desk now draws a chart with the `frappe.chart` island ([0015](0015-framework-builds-its-own-islands.md)), through one call, `frappe.ui.chart(el, config)`.

## Decision

The chart config is frappe-ui's: the props of the chart component `type` names (`bar`, `line`, `area`, `donut`, `funnel`, `heatmap`, `calendar-heatmap`, `sankey`, `scatter`), plus `fieldtype`, `options`, `precision` and `height`. It is JSON only, so a report or a Dashboard Chart can store it and the server can send it.

Values read the way desk prints a field. `fieldtype`, `options` and `precision`, on the chart or on one series, form the df desk's formatter reads, and the island calls it through the desk context (`format`, `format_axis_number`). A value axis is shortened and reads as its first series, so a Currency axis keeps its symbol. A config never carries a function. The config is the doc the formatter reads, so `options: "currency"` takes the chart's `currency`, as report charts already send it. `currency` alone implies `fieldtype: "Currency"`. `echartOptions` passes through to frappe-ui but is not part of the contract: it couples a saved config to echarts' option tree.

The frappe-charts shape (`data.labels` / `data.datasets`, heatmap `data.dataPoints`) is an input, not a second contract. `legacy_config.js` converts it inside the island, in one place, and every render point and every saved `custom_options` goes through that one conversion. A key it has no equivalent for is dropped. In developer mode it warns once per key. A frappe-charts pie draws as a donut.

The flag lives in `frappe.ui.chart` and nowhere else. A legacy config draws with frappe-charts while System Settings' `use_classic_charts` is on. Any other config always draws with the island. Render points call `frappe.ui.chart` unconditionally. A caller whose classic path differs asks `frappe.ui.chart.is_classic(config)`, so the setting's name stays in one file. A classic chart's handle is the `frappe.Chart` itself, so an app that reaches into it keeps working while the setting is on. The island's handle for a legacy config keeps the `data` and `draw()` that apps already reach for, and nothing else of `frappe.Chart`.

`frappe.Chart`, `frappe.utils.make_chart` and `frappe.ui.RealtimeChart` stay frappe-charts, unchanged. Apps that call them keep what they draw.

## Rejected: the frappe-charts shape stays the contract

Every render point already builds it, so converting at the island would be the whole change.

It makes the conversion permanent. Its option names describe frappe-charts' drawing (`regionFill`, `spaceRatio`, `xAxisMode`), and its formatting is functions, which no stored config can hold. Each frappe-ui feature would need a frappe-charts-shaped name first. As an input it can shrink to nothing; as the contract it cannot.

## Rejected: `frappe.Chart` becomes a compat shim

Point `frappe.Chart` at the island, so every caller in every app moves at once.

`frappe.Chart` is frappe-charts' API: `addDataPoint`, `removeDataPoint`, `export()`, its DOM, and the class `RealtimeChart` extends. An app that reaches into any of these breaks with no flag to turn back. A new call is opt-in by the caller, and the old one is still there for what the new one cannot do.

## Rejected: a flag at each render point

Each render point checks the setting and picks its chart.

Seven render points then hold seven copies of one rule, and an app that adopts `frappe.ui.chart` has to copy it an eighth time. Removing classic charts means finding every copy. With the check in one call, removing it is one deletion.
