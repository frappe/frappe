import { ref, onMounted } from "vue"

const REPORT_FUNCTIONS = {
	Sum: (values) => values.reduce((total, value) => total + value, 0),
	Average: (values) => values.reduce((total, value) => total + value, 0) / (values.length || 1),
	Minimum: (values) => Math.min(...values),
	Maximum: (values) => Math.max(...values),
}

export default {
	props: {
		card: { type: String, default: "", meta: { description: "The name of a Number Card" } },
		label: { type: String, default: "" },
		// the server adds the fields of the Number Card
		doc: { type: Object, default: () => ({}) },
	},
	setup(props) {
		const desk = window.frappe
		const value = ref("")
		const loading = ref(true)
		let filters = null
		let customRoute = null

		onMounted(async () => {
			try {
				filters = desk.dashboard_utils.get_all_filters(props.doc)
				value.value = formatNumber(await fetchNumber())
			} catch (error) {
				console.error(`Number card ${props.card} did not load`, error)
				value.value = "-"
			}
			loading.value = false
		})

		async function fetchNumber() {
			const doc = props.doc
			if (doc.type === "Custom") {
				const result = await desk.xcall(doc.method, { filters })
				if (result && typeof result === "object") {
					customRoute = result
					return result.value
				}
				return result
			}
			if (doc.type === "Report") {
				const report = await desk.xcall("frappe.desk.query_report.run", {
					report_name: doc.report_name,
					filters,
					ignore_prepared_report: 1,
				})
				const values = report.result.map((row) => row[doc.report_field]).filter((number) => number)
				return REPORT_FUNCTIONS[doc.report_function || "Sum"](values)
			}
			return desk.xcall("frappe.desk.doctype.number_card.number_card.get_result", { doc, filters })
		}

		function formatNumber(number) {
			if (typeof number !== "number") return number ?? "-"
			if (props.doc.show_full_number) return window.format_number(number)
			const [digits, unit] = desk.utils.shorten_number(number, desk.sys_defaults.country, 5).split(" ")
			const text = props.doc.currency ? window.format_currency(parseFloat(digits), props.doc.currency) : digits
			return unit ? `${text} ${unit}` : text
		}

		function open() {
			const doc = props.doc
			if (doc.type === "Custom") {
				if (!customRoute?.route) return
				if (customRoute.route_options) desk.route_options = customRoute.route_options
				return desk.set_route(customRoute.route)
			}
			const isReport = doc.type === "Report"
			if (isReport && filters) desk.route_options = filters
			if (!isReport) desk.route_options = getListFilters()
			desk.set_route(
				desk.utils.generate_route({
					name: isReport ? doc.report_name : doc.document_type,
					type: isReport ? "report" : "doctype",
					is_query_report: isReport,
				}),
			)
		}

		// several filters on one field become one list of conditions for the list view
		function getListFilters() {
			const options = {}
			for (const filter of filters || []) (options[filter[1]] ||= []).push([filter[2], filter[3]])
			return options
		}

		return { value, loading, open }
	},
}
