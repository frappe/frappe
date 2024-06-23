import { ModuleSidebarLink, Route } from "@/types"

export function slug(name: string): string {
	return name.toLowerCase().replace(/ /g, "-")
}

export function getRoute(link: ModuleSidebarLink, module: string): Route | undefined {
	// TODO: handle single doctypes - shouldn't be a list
	if (link.workspace) {
		return { name: "Workspace", params: { workspace: slug(link.workspace) } }
	} else if (link.link_type === "DocType") {
		return {
			name: "ListView",
			params: {
				doctype: slug(link.link_to),
			},
		}
	} else if (["Page", "Report", "Dashboard"].includes(link.link_type)) {
		return {
			name: link.link_type,
			params: { module: slug(module), id: slug(link.link_to) },
		}
	}
}
