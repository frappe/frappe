export function slug(name) {
	return name.toLowerCase().replace(/ /g, "-")
}

export function getRoute(link, module) {
	// TODO: handle single doctypes - shouldn't be a list
	// slug in routes for everything - cleaner way to look up slugs
	if (link.workspace) {
		return { name: "Workspace", params: { name: link.workspace } }
	} else if (link.link_type === "DocType") {
		return {
			name: "List",
			params: {
				module: module,
				id: link.link_to,
			},
		}
	} else if (["Page", "Report", "Dashboard"].includes(link.link_type)) {
		return {
			name: link.link_type,
			params: { module: module, id: link.link_to },
		}
	}
}
