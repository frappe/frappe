import { ref, onMounted } from "vue"

export default {
	props: {
		label: { type: String, default: "Shortcut" },
		type: {
			type: String,
			default: "DocType",
			meta: { control: "select", options: ["DocType", "Report", "Page", "Dashboard", "URL"] },
		},
		link_to: { type: String, default: "" },
		url: { type: String, default: "" },
		doc_view: { type: String, default: "" },
		kanban_board: { type: String, default: "" },
		stats_filter: { type: String, default: "", meta: { description: "Filters as JSON. The shortcut shows the count" } },
		format: { type: String, default: "", meta: { description: "The count's text, such as {} Open" } },
		color: { type: String, default: "" },
		is_query_report: { type: [Number, Boolean], default: 0 },
		ref_doctype: { type: String, default: "" },
		report_ref_doctype: { type: String, default: "" },
	},
	setup(props) {
		const desk = window.frappe
		const count = ref("")

		onMounted(async () => {
			if (props.type !== "DocType" || !props.stats_filter) return
			const filters = desk.utils.process_filter_expression(props.stats_filter)
			const total = await desk.db.count(props.link_to, { filters })
			if (total) count.value = (props.format || "{}").replace("{}", desk.utils.shorten_number(total))
		})

		function open() {
			if (props.type === "URL") return window.open(props.url, "_blank")
			const route = desk.utils.generate_route({
				name: props.link_to,
				type: props.type,
				is_query_report: props.is_query_report,
				doctype: props.ref_doctype,
				doc_view: props.doc_view,
				kanban_board: props.kanban_board,
				report_ref_doctype: props.report_ref_doctype,
			})
			const filters = desk.utils.get_filter_from_json(props.stats_filter)
			if (props.type === "DocType" && filters) desk.route_options = filters
			desk.set_route(route)
		}

		return { count, open }
	},
}
