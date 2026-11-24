import { createListResource } from "frappe-ui"

export default {
	props: {
		label: { type: String, default: "" },
		document_type: { type: String, default: "", meta: { description: "The DocType to list" } },
		quick_list_filter: { type: String, default: "", meta: { description: "Filters as JSON" } },
		// the server adds the DocType's title field
		title_field: { type: String, default: "" },
	},
	setup(props) {
		const desk = window.frappe
		const titleField = props.title_field || "name"
		const documents = createListResource({
			doctype: props.document_type,
			fields: [...new Set(["name", "modified", titleField])],
			filters: desk.utils.get_filter_from_json(props.quick_list_filter, props.document_type) || {},
			orderBy: "modified desc",
			pageLength: 4,
			auto: true,
		})

		function getTitle(row) {
			return row[titleField] || row.name
		}

		function getAge(row) {
			return desk.datetime.prettyDate(row.modified)
		}

		function open(row) {
			desk.set_route("Form", props.document_type, row.name)
		}

		function openList() {
			desk.route_options = desk.utils.get_filter_from_json(props.quick_list_filter, props.document_type)
			desk.set_route("List", props.document_type)
		}

		function add() {
			desk.new_doc(props.document_type)
		}

		return { documents, getTitle, getAge, open, openList, add }
	},
}
