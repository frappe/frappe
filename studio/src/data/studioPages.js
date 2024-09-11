import { createListResource } from "frappe-ui"

const studioPages = createListResource({
	method: "GET",
	doctype: "Studio Page",
	fields: ["name", "page_title", "route", "modified"],
	auto: true,
	cache: "pages",
	orderBy: "modified desc",
	pageLength: 50,
})

export { studioPages }
