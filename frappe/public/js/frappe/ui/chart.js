import { Chart } from "frappe-charts/dist/frappe-charts.esm";

import { is_legacy_chart_config } from "./island/chart/legacy_config.js";

frappe.provide("frappe.ui");
frappe.Chart = Chart;

/**
 * Draws a chart into `el` and returns its handle at once.
 *
 *     const chart = frappe.ui.chart(el, { type: "bar", data: rows, x: "month", y: "total" });
 *     chart.update(config);
 *     chart.destroy();
 *
 * `config` is a frappe-ui chart config. A frappe-charts config (`data.labels` /
 * `data.datasets`, heatmap `data.dataPoints`) is converted, and its handle also carries `data`
 * and `draw()`. While System Settings keeps classic charts, frappe-charts draws it and the
 * handle is the `frappe.Chart` itself. See
 * ui/island/decisions/0016-desk-charts-are-frappe-ui-charts.md.
 *
 * @param {HTMLElement|JQuery} el
 * @param {Object} config
 * @returns {{ update: (config: Object) => void, destroy: () => void, ready: Promise }}
 */
frappe.ui.chart = function (el, config) {
	const target = el?.jquery ? el[0] : el;
	if (!is_legacy_chart_config(config)) return island_chart(target, config);
	if (frappe.ui.chart.is_classic(config)) return classic_chart(target, config);
	return legacy_island_chart(target, config);
};

/** Whether `frappe.ui.chart` draws `config` with frappe-charts, for a caller that styles its markup. */
frappe.ui.chart.is_classic = (config) =>
	is_legacy_chart_config(config) && frappe.defaults.is_enabled("use_classic_charts");

function island_chart(el, config) {
	el.classList.add("frappe-ui-chart");
	const island = frappe.ui.mount_island("frappe.chart", el, { config });
	const handle = {
		// a new object, so a config changed in place and passed again still redraws
		update: (next) => island.update({ config: { ...next } }),
		destroy: () => {
			island.unmount();
			el.classList.remove("frappe-ui-chart");
		},
	};
	handle.ready = island.ready.then(() => handle);
	handle.ready.catch((error) => show_error(el, error));
	return handle;
}

let logged_error = false;

// the error names a build step: console once, screen only in developer mode
function show_error(el, error) {
	if (!logged_error) {
		console.error('could not draw a chart with the "frappe.chart" island', error);
		logged_error = true;
	}

	$(el)
		.empty()
		.append(
			frappe.ui.empty_state({
				icon: "package",
				title: __("This chart has not been built"),
				description: frappe.boot.developer_mode
					? error.message
					: __("Its assets are missing. Build the app that ships it."),
			})
		);
}

/** A legacy `update` takes a frappe-charts `data` object, or a whole config. */
function legacy_island_chart(el, config) {
	let current = config;
	const handle = island_chart(el, config);
	const update_island = handle.update;
	Object.defineProperty(handle, "data", { get: () => current.data });
	handle.update = (next) => {
		current = next.data ? next : { ...current, data: next };
		update_island(current);
	};
	handle.draw = () => {};
	return handle;
}

function classic_chart(el, config) {
	const chart = new frappe.Chart(el, config);
	chart.ready = Promise.resolve(chart);
	return chart;
}

frappe.ui.RealtimeChart = class RealtimeChart extends frappe.Chart {
	constructor(element, socketEvent, maxLabelPoints = 8, data) {
		super(element, data);
		if (data.data.datasets[0].values.length > maxLabelPoints) {
			frappe.throw(
				__(
					"Length of passed data array is greater than value of maximum allowed label points!"
				)
			);
		}
		this.currentSize = data.data.datasets[0].values.length;
		this.socketEvent = socketEvent;
		this.maxLabelPoints = maxLabelPoints;

		this.start_updating = function () {
			frappe.realtime.on(this.socketEvent, (data) => {
				this.update_chart(data.label, data.points);
			});
		};

		this.stop_updating = function () {
			frappe.realtime.off(this.socketEvent);
		};

		this.update_chart = function (label, data) {
			if (this.currentSize >= this.maxLabelPoints) {
				this.removeDataPoint(0);
			} else {
				this.currentSize++;
			}
			this.addDataPoint(__(label), data);
		};
	}
};
