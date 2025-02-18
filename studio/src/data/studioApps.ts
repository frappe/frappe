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

export { studioApps }
