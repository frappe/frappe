import { createListResource } from "frappe-ui"

const studioWatchers = createListResource({
	doctype: "Studio Page Watcher",
	parent: "Studio Page",
	fields: ["name", "source", "script", "immediate", "parent"],
	orderBy: "modified desc",
	pageLength: 50,
})

export { studioWatchers }