export function slug(name) {
	return name.toLowerCase().replace(/ /g, "-")
}

export function getRoute(link, module) {
	// TODO: handle single doctypes - shouldn't be a list
	if (link.workspace) {
		return { name: "Workspace", params: { name: slug(link.workspace) } }
	} else if (link.link_type === "DocType") {
		return {
			name: "List",
			params: {
				module: module,
				id: slug(link.link_to),
			},
		}
	} else if (["Page", "Report", "Dashboard"].includes(link.link_type)) {
		return {
			name: link.link_type,
			params: { module: module, id: slug(link.link_to) },
		}
	}
}
