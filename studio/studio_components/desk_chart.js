import { ref, computed, onMounted } from "vue"

export default {
	props: {
		chart: { type: String, default: "", meta: { description: "The name of a Dashboard Chart" } },
		label: { type: String, default: "" },
		// the server adds the fields of the Dashboard Chart
		doc: { type: Object, default: () => ({}) },
	},
	setup(props) {
		const desk = window.frappe
		const rows = ref([])
		const series = ref([])
		const message = ref("Loading")
		const kind = computed(() => {
			if (message.value) return ""
			if (["Pie", "Donut", "Percentage"].includes(props.doc.type)) return "donut"
			return props.doc.type === "Line" ? "line" : "bar"
		})

		onMounted(async () => {
			try {
				setData(await fetchData())
				message.value = rows.value.length ? "" : "No data"
			} catch (error) {
				console.error(`Chart ${props.chart} did not load`, error)
				message.value = "This chart did not load"
			}
		})

		async function fetchData() {
			const doc = props.doc
			if (doc.chart_type === "Custom") throw new Error("A chart with its own source is not supported")
			if (doc.chart_type !== "Report") {
				return desk.xcall("frappe.desk.doctype.dashboard_chart.dashboard_chart.get", { chart_name: props.chart })
			}
			const report = await desk.xcall("frappe.desk.query_report.run", {
				report_name: doc.report_name,
				filters: desk.dashboard_utils.get_all_filters(doc),
				ignore_prepared_report: 1,
			})
			if (doc.use_report_chart) return report.chart?.data
			return {
				labels: report.result.map((row) => row[doc.x_field]),
				datasets: doc.y_fields.map((field) => ({
					name: report.columns.find((column) => column.fieldname === field)?.label || field,
					values: report.result.map((row) => row[field]),
				})),
			}
		}

		// one row for each label, with one key for each dataset
		function setData(data) {
			const datasets = (data?.datasets || []).map((dataset, index) => ({
				name: dataset.name || props.label || `Series ${index + 1}`,
				values: dataset.values || [],
			}))
			series.value = datasets.map((dataset) => dataset.name)
			rows.value = (data?.labels || []).map((label, index) => ({
				label: String(label ?? ""),
				...Object.fromEntries(datasets.map((dataset) => [dataset.name, dataset.values[index] ?? 0])),
			}))
		}

		function open() {
			desk.set_route("Form", "Dashboard Chart", props.chart)
		}

		return { rows, series, kind, message, open }
	},
}
