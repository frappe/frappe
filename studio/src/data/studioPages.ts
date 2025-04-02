import { createListResource } from "frappe-ui"

const studioPages = createListResource({
	method: "GET",
	doctype: "Studio Page",
	fields: ["name", "page_title", "route", "studio_app", "creation", "modified"],
	auto: true,
	cache: "pages",
	orderBy: "creation asc",
	pageLength: 50,
})

export { studioPages }
