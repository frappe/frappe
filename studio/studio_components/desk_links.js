export default {
	props: {
		label: { type: String, default: "Links" },
		links: {
			type: Array,
			default: () => [],
			meta: { description: "Rows of label, link_type (DocType, Report or Page) and link_to" },
		},
	},
	setup() {
		const desk = window.frappe

		// a link waits for the records that it depends on
		function isDisabled(link) {
			return Boolean(link.dependencies && link.incomplete_dependencies?.length)
		}

		function getHint(link) {
			if (!isDisabled(link)) return ""
			return "Make these first: " + link.incomplete_dependencies.join(", ")
		}

		function open(link) {
			if (isDisabled(link)) return
			const isReport = link.link_type === "Report"
			desk.set_route(
				desk.utils.generate_route({
					name: link.link_to,
					type: link.link_type,
					is_query_report: link.is_query_report,
					report_ref_doctype: link.report_ref_doctype,
					doctype: isReport && !link.is_query_report ? link.dependencies : undefined,
				}),
			)
		}

		return { isDisabled, getHint, open }
	},
}
