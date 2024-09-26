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

const studioAppScreens = createListResource({
	doctype: "Studio App Screen",
	parent: "Studio App",
	fields: ["screen.page_title as screen_title", "screen.route", "screen.name as screen_name", "name"],
})

export { studioApps, studioAppScreens }
