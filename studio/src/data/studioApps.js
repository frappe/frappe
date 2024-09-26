import { createListResource } from "frappe-ui"

const studioApps = createListResource({
	method: "GET",
	doctype: "Studio App",
	fields: ["name", "app_title", "route", "app_home", "creation", "modified"],
	auto: true,
	cache: "apps",
	orderBy: "modified desc",
	pageLength: 50,
})

const studioAppPages = createListResource({
	doctype: "Studio App Page",
	parent: "Studio App",
	fields: [
		"studio_page.page_title as page_title",
		"studio_page.route",
		"studio_page.name as page_name",
		"name",
	],
})

export { studioApps, studioAppPages }
