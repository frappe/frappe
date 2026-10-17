// node --test frappe/public/js/frappe/ui/island/chart/legacy_config.test.mjs
// The configs are real ones, from the frappe and erpnext code named above each test.

import assert from "node:assert/strict";
import { describe, test } from "node:test";

import { from_legacy_config, is_legacy_chart_config } from "./legacy_config.js";

// a heatmap's unix-second keys read in the browser's zone
process.env.TZ = "Asia/Kolkata";

const convert = from_legacy_config;

describe("is_legacy_chart_config", () => {
  test("rows in an array are a frappe-ui config", () => {
    assert.equal(
      is_legacy_chart_config({ type: "bar", data: [], x: "a", y: "b" }),
      false
    );
  });

  test("labels and datasets, a heatmap and an empty data object are legacy", () => {
    assert.equal(
      is_legacy_chart_config({ data: { labels: [], datasets: [] } }),
      true
    );
    assert.equal(
      is_legacy_chart_config({ type: "heatmap", data: { dataPoints: {} } }),
      true
    );
    assert.equal(is_legacy_chart_config({ type: "heatmap", data: {} }), true);
  });

  test("no data is neither", () => {
    assert.equal(is_legacy_chart_config({}), false);
    assert.equal(is_legacy_chart_config(undefined), false);
  });
});

describe("axis charts", () => {
  // frappe/website/report/website_analytics/website_analytics.py
  test("website analytics: axis-mixed lines with a region fill become an area chart", () => {
    const config = convert({
      data: {
        labels: ["Oct 01 2026", "Oct 02 2026"],
        datasets: [
          { name: "Total Views", type: "line", values: [12, 30] },
          { name: "Unique Visits", type: "line", values: [4, 9] },
        ],
      },
      type: "axis-mixed",
      lineOptions: { regionFill: 1 },
      axisOptions: { xIsSeries: 1 },
      colors: ["#7cd6fd", "#5e64ff"],
    });

    assert.deepEqual(config, {
      type: "area",
      data: [
        { label: "Oct 01 2026", series_1: 12, series_2: 4 },
        { label: "Oct 02 2026", series_1: 30, series_2: 9 },
      ],
      x: "label",
      y: ["series_1", "series_2"],
      seriesConfig: {
        series_1: { label: "Total Views", color: "#7cd6fd" },
        series_2: { label: "Unique Visits", color: "#5e64ff" },
      },
      height: 240,
    });
  });

  test("axis-mixed with a bar and a line keeps a bar chart and marks the line", () => {
    // erpnext reports set datasets[].chartType
    const config = convert({
      type: "axis-mixed",
      data: {
        labels: ["Q1", "Q2"],
        datasets: [
          { name: "Revenue", values: [10, 20], chartType: "bar" },
          { name: "Margin", values: [2, 5], chartType: "line" },
        ],
      },
    });

    assert.equal(config.type, "bar");
    assert.deepEqual(config.seriesConfig, {
      series_1: { label: "Revenue" },
      series_2: { label: "Margin", type: "line" },
    });
    assert.equal(config.xAxis.type, "category");
  });

  // erpnext/buying/report/requested_items_to_order_and_receive
  test("a stacked bar", () => {
    const config = convert({
      data: {
        labels: ["ITEM-0001", "ITEM-0002"],
        datasets: [
          { name: "Qty to Order", values: [5, 0] },
          { name: "Ordered Qty", values: [3, 2] },
          { name: "Received Qty", values: [1, 2] },
          { name: "Qty to Receive", values: [2, 0] },
        ],
      },
      type: "bar",
      barOptions: { stacked: 1 },
    });

    assert.equal(config.type, "bar");
    assert.equal(config.stacked, true);
    assert.deepEqual(config.y, [
      "series_1",
      "series_2",
      "series_3",
      "series_4",
    ]);
    assert.deepEqual(config.data[1], {
      position: 1,
      series_1: 0,
      series_2: 2,
      series_3: 2,
      series_4: 0,
    });
    assert.equal(config.xAxis.format(1), "ITEM-0002");
  });

  // frappe/public/js/frappe/views/reports/report_utils.js, "Set Chart" with a repeating X field
  test("rows that share a label stay apart, in their order, each printed with its label", () => {
    const config = convert({
      type: "bar",
      data: {
        labels: ["A", "B", "A", "B", "C", "A"],
        datasets: [{ values: [1, 2, 3, 4, 5, 6] }],
      },
    });

    assert.equal(config.x, "position");
    assert.deepEqual(
      config.data.map((row) => [
        config.xAxis.format(row[config.x]),
        row.series_1,
      ]),
      [
        ["A", 1],
        ["B", 2],
        ["A", 3],
        ["B", 4],
        ["C", 5],
        ["A", 6],
      ]
    );
  });

  // frappe/utils/goal.py, drawn by form/dashboard.js render_graph
  test("goal graph: yMarkers become reference lines, its summary and formatted values go", () => {
    const unknown = [];
    const config = convert(
      {
        title: "Sales this month",
        data: {
          datasets: [
            { values: [100, 250], formatted: ["₹ 100.00", "₹ 250.00"] },
          ],
          labels: ["Sep 26", "Oct 26"],
          yMarkers: [{ label: "Goal", lineType: "dashed", value: 300 }],
        },
        summary: [{ title: "Completed", color: "green", value: "83%" }],
        type: "line",
        colors: ["green"],
        truncateLegends: 1,
        axisOptions: {
          shortenYAxisNumbers: 1,
          numberFormatter: (value) => String(value),
        },
      },
      { on_unknown_key: (key) => unknown.push(key) }
    );

    assert.deepEqual(unknown, []);
    assert.equal(config.type, "line");
    assert.equal(config.title, "Sales this month");
    assert.deepEqual(config.referenceLines, [
      { value: 300, label: "Goal", dashed: true },
    ]);
    assert.deepEqual(config.seriesConfig, {
      series_1: { color: "var(--chart-categorical-3)" },
    });
    assert.equal("summary" in config, false);
  });

  // erpnext/accounts/report/profit_and_loss_statement
  test("a report chart in a currency formats as that currency", () => {
    const config = convert({
      data: {
        labels: ["2025-2026"],
        datasets: [
          { name: "Income", values: [1200000.5] },
          { name: "Expense", values: [800000] },
          { name: "Net Profit/Loss", values: [400000.5] },
        ],
      },
      type: "bar",
      fieldtype: "Currency",
      options: "currency",
      currency: "INR",
    });

    assert.equal(config.fieldtype, "Currency");
    assert.equal(config.options, "currency");
    assert.equal(config.currency, "INR");
  });

  test("a currency alone formats as Currency, read from the config", () => {
    // chart_widget.js: a Dashboard Chart with a currency set
    const config = convert({
      type: "line",
      currency: "USD",
      data: { labels: ["a"], datasets: [{ values: [1] }] },
    });

    assert.equal(config.fieldtype, "Currency");
    assert.equal(config.options, "currency");
    assert.equal(config.currency, "USD");
  });

  // frappe/core/doctype/error_log/error_log.js
  test("error log timeline: a short series bar chart", () => {
    const unknown = [];
    const config = convert(
      {
        type: "bar",
        height: 160,
        colors: ["#e24c4c"],
        axisOptions: { xIsSeries: 1, xAxisMode: "tick" },
        data: {
          labels: ["2026-10-16", "2026-10-17"],
          datasets: [{ values: [0, 4] }],
        },
      },
      { on_unknown_key: (key) => unknown.push(key) }
    );

    assert.deepEqual(unknown, []);
    assert.equal(config.height, 160);
    assert.equal(config.xAxis, undefined);
    assert.deepEqual(config.seriesConfig, { series_1: { color: "#e24c4c" } });
  });

  // frappe/public/js/frappe/views/reports/report_view.js
  test("report view: preset colour names and a tooltip function", () => {
    const unknown = [];
    const config = convert(
      {
        data: {
          labels: ["Open", "Closed"],
          datasets: [
            { name: "Count", values: [3, 7] },
            { name: "Total", values: [30, 70] },
            { name: "Extra", values: [1, 1] },
            { name: "Other", values: [0, 1] },
          ],
        },
        type: "bar",
        colors: ["#70E078", "light-blue", "orange", "red"],
        title: "",
        truncateLegends: 1,
        axisOptions: { shortenYAxisNumbers: 1, numberFormatter: () => "" },
        tooltipOptions: { formatTooltipY: (value) => value },
      },
      { on_unknown_key: (key) => unknown.push(key) }
    );

    assert.deepEqual(unknown, []);
    assert.equal("title" in config, false);
    assert.deepEqual(
      Object.values(config.seriesConfig).map((series) => series.color),
      [
        "#70E078",
        "var(--chart-categorical-2)",
        "var(--chart-categorical-7)",
        "var(--chart-categorical-9)",
      ]
    );
  });

  test("lineOptions: spline smooths, hideDots is frappe-ui's own default", () => {
    const config = convert({
      type: "line",
      lineOptions: { spline: 1, hideDots: 1 },
      data: { labels: ["a", "b"], datasets: [{ name: "x", values: [1, 2] }] },
    });

    assert.equal(config.type, "line");
    assert.equal(config.smooth, true);
    assert.equal("showDataPoints" in config, false);
  });

  test("barOptions.horizontal, valuesOverPoints and a dataset colour", () => {
    // chart_widget.js sets valuesOverPoints from show_values_over_chart
    const config = convert({
      type: "bar",
      barOptions: { horizontal: 1, spaceRatio: 0.3 },
      valuesOverPoints: 1,
      colors: ["blue"],
      data: {
        labels: ["a"],
        datasets: [{ name: "x", values: [1], color: "#123456" }],
      },
    });

    assert.equal(config.horizontal, true);
    assert.equal(config.showDataLabels, true);
    assert.equal(config.seriesConfig.series_1.color, "#123456");
  });

  test("values: missing and non-numeric draw as 0, null stays a gap, strings are numbers", () => {
    const config = convert({
      type: "line",
      data: {
        labels: ["a", "b", "c", "d"],
        datasets: [{ values: ["2.5", null, "x"] }],
      },
    });

    assert.deepEqual(
      config.data.map((row) => row.series_1),
      [2.5, null, 0, 0]
    );
  });

  test("no type is frappe-charts' line", () => {
    assert.equal(convert({ data: { labels: [], datasets: [] } }).type, "line");
  });

  test("no labels is an empty chart, not an error", () => {
    assert.deepEqual(convert({ type: "bar", data: {} }).data, []);
  });

  test("an unknown type throws", () => {
    assert.throws(
      () => convert({ type: "radar", data: {} }),
      /Unknown chart type "radar"/
    );
  });
});

describe("slice charts", () => {
  // erpnext/crm/dashboard_chart/lead_source, drawn by chart_widget.js
  test("a donut with maxSlices and colours that stay on their labels", () => {
    const unknown = [];
    const config = convert(
      {
        type: "donut",
        truncateLegends: 1,
        maxSlices: 8,
        height: 240,
        colors: ["red", "blue", "#00ff00"],
        data: {
          labels: ["Campaign", "Website", "Cold Calling"],
          datasets: [{ name: "Lead Source", values: [2, 9, 4] }],
        },
      },
      { on_unknown_key: (key) => unknown.push(key) }
    );

    assert.deepEqual(unknown, []);
    assert.deepEqual(config, {
      type: "donut",
      data: [
        { label: "Website", "Lead Source": 9 },
        { label: "Cold Calling", "Lead Source": 4 },
        { label: "Campaign", "Lead Source": 2 },
      ],
      category: "label",
      value: "Lead Source",
      centerLabel: "Total",
      maxSlices: 8,
      palette: [
        "var(--chart-categorical-1)",
        "#00ff00",
        "var(--chart-categorical-9)",
      ],
      height: 240,
    });
  });

  test("a pie is a donut that sums every dataset per label and fills missing colours from frappe-ui's ramp", () => {
    const config = convert({
      type: "pie",
      colors: ["orange"],
      data: {
        labels: ["a", "b"],
        datasets: [
          { name: "x", values: [1, 5] },
          { name: "y", values: [1, 0] },
        ],
      },
    });

    assert.equal(config.type, "donut");
    assert.equal(config.value, "value");
    assert.deepEqual(config.data, [
      { label: "b", value: 5 },
      { label: "a", value: 2 },
    ]);
    assert.deepEqual(config.palette, [
      "var(--chart-categorical-2)",
      "var(--chart-categorical-7)",
    ]);
  });

  test("the caller's caption names the total in the hole", () => {
    const config = convert(
      {
        type: "donut",
        data: { labels: ["a"], datasets: [{ name: "Orders", values: [1] }] },
      },
      { center_label: "Gesamt" }
    );

    assert.equal(config.centerLabel, "Gesamt");
  });

  test("no colours leaves frappe-ui's palette", () => {
    const config = convert({
      type: "donut",
      data: { labels: ["a"], datasets: [{ values: [1] }] },
    });

    assert.equal("palette" in config, false);
  });

  // erpnext/projects/report/delayed_tasks_summary
  test("percentage: one normalized horizontal bar with a share per label", () => {
    const config = convert({
      data: {
        labels: ["On Track", "Delayed"],
        datasets: [{ name: "Delayed", values: [7, 3] }],
      },
      type: "percentage",
      colors: ["#84D5BA", "#CB4B5F"],
      maxSlices: 6,
    });

    assert.deepEqual(config, {
      type: "bar",
      data: [
        { label: "", category: "On Track", value: 7 },
        { label: "", category: "Delayed", value: 3 },
      ],
      x: "label",
      y: "value",
      splitBy: "category",
      maxSeries: 6,
      seriesConfig: {
        "On Track": { color: "#84D5BA" },
        Delayed: { color: "#CB4B5F" },
      },
      stacked: "normalized",
      horizontal: true,
      height: 240,
    });
  });
});

describe("heatmap", () => {
  const today = new Date(2026, 9, 17);
  // midnight in Asia/Kolkata, as MariaDB's UNIX_TIMESTAMP(DATE(...)) gives them there
  const oct_1 = Date.UTC(2026, 8, 30, 18, 30) / 1000;
  const oct_2 = oct_1 + 86400;

  // dashboard_chart.py get_heatmap_chart_config, ranged by chart_widget.js
  test("dashboard chart: unix-second keys and a range in data", () => {
    const config = convert(
      {
        type: "heatmap",
        height: 240,
        colors: ["#ebedf0", "#c6e48b", "#7bc96f", "#239a3b", "#196127"],
        data: {
          labels: [],
          dataPoints: { [oct_1]: 3, [oct_2]: 5 },
          start: new Date(2026, 0, 1),
          end: new Date(2026, 11, 31),
        },
      },
      { today }
    );

    assert.deepEqual(config, {
      type: "calendar-heatmap",
      data: [
        { date: "2026-10-01", value: 3 },
        { date: "2026-10-02", value: 5 },
      ],
      date: "date",
      value: "value",
      start: "2026-01-01",
      end: "2026-12-31",
      palette: ["#ebedf0", "#c6e48b", "#7bc96f", "#239a3b", "#196127"],
      height: 240,
    });
  });

  // form/dashboard.js render_heatmap, then update_heatmap with the timeline data
  test("form dashboard: a top-level start, count_label, and the year up to today", () => {
    const unknown = [];
    const config = convert(
      {
        type: "heatmap",
        start: new Date(2025, 9, 17),
        count_label: "interactions",
        discreteDomains: 1,
        radius: 3,
        data: { dataPoints: { [oct_1]: 1 } },
      },
      { today, on_unknown_key: (key) => unknown.push(key) }
    );

    assert.deepEqual(unknown, []);
    assert.equal(config.value, "interactions");
    assert.deepEqual(config.data, [{ date: "2026-10-01", interactions: 1 }]);
    assert.equal(config.start, "2025-10-17");
    assert.equal(config.end, "2026-10-17");
    assert.equal("palette" in config, false);
  });

  test("no range is frappe-charts' year up to today; day keys stay as given", () => {
    const config = convert(
      {
        type: "heatmap",
        countLabel: "edits",
        data: { dataPoints: { "2026-05-04": 2 } },
      },
      { today }
    );

    assert.equal(config.start, "2025-10-17");
    assert.equal(config.end, "2026-10-17");
    assert.deepEqual(config.data, [{ date: "2026-05-04", edits: 2 }]);
  });

  test("no data points is an empty calendar", () => {
    const config = convert({ type: "heatmap", data: {} }, { today });
    assert.deepEqual(config.data, []);
  });
});

describe("unknown keys", () => {
  test("are reported with their path, and dropped", () => {
    const unknown = [];
    const config = convert(
      {
        type: "bar",
        isNavigable: 1,
        onClick: () => {},
        lineOptions: { heatline: 1 },
        data: {
          labels: ["a"],
          datasets: [{ values: [1], axisPosition: "right" }],
          yRegions: [],
        },
      },
      { on_unknown_key: (key) => unknown.push(key) }
    );

    assert.deepEqual(unknown.sort(), [
      "data.datasets[].axisPosition",
      "data.yRegions",
      "isNavigable",
      "lineOptions.heatline",
    ]);
    assert.equal("isNavigable" in config, false);
  });

  test("the junk Set Chart saves into custom_options is known", () => {
    const unknown = [];
    convert(
      {
        type: "bar",
        x_field: "status",
        y_fields: ["count"],
        y_axis_fields: [{ y_field: "count", color: "blue" }],
        chart_type: "Bar",
        data: { labels: [], datasets: [] },
      },
      { on_unknown_key: (key) => unknown.push(key) }
    );

    assert.deepEqual(unknown, []);
  });
});
