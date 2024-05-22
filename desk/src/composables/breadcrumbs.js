import { computed } from "vue"
import { workspacesBySlug, doctypesBySlug, modulesBySlug, reportsBySlug } from "@/data/permissions"

export function useBreadcrumbs(route) {
	const breadcrumbs = computed(() => {
		if (route.name === "Home") return []

		const items = [{ label: "Home", route: { name: "Home" } }]

		switch (route.name) {
			case "Workspace":
				setWorkspaceBreadcrumb(items)
				break
			case "ListView":
				setListBreadcrumb(items)
				break
			case "Form":
				setFormBreadcrumb(items)
				break
			case "Report":
				setReportBreadcrumb(items)
				break
			case "Page":
			case "Dashboard":
				setModuleBreadcrumb(items)
				break
			default:
				break
		}

		return items
	})

	function setModuleBreadcrumb(items, module = "") {
		const moduleName = module || modulesBySlug[route.params.module]
		items.push({
			label: moduleName,
			route: {
				name: "Module",
				params: {
					module: moduleName,
				},
			},
		})
	}

	function setWorkspaceBreadcrumb(items) {
		const workspace = workspacesBySlug[route.params.workspace]
		setModuleBreadcrumb(items, workspace.module)

		items.push({
			label: workspace.name,
			route: {
				name: "Workspace",
				params: {
					workspace: workspace.name,
				},
			},
		})
	}

	function setListBreadcrumb(items) {
		const doctype = doctypesBySlug[route.params.doctype]
		setModuleBreadcrumb(items, doctype.module)

		items.push({
			label: doctype.name,
			route: {
				name: "ListView",
				params: {
					doctype: route.params.doctype,
				},
			},
		})
	}

	function setFormBreadcrumb(items) {
		setListBreadcrumb(items)
		items.push({
			label: route.params.id,
			route: {
				name: "Form",
				params: {
					doctype: route.params.doctype,
					name: route.params.id,
				},
			},
		})
	}

	function setReportBreadcrumb(items) {
		const report = reportsBySlug[route.params.id]
		setModuleBreadcrumb(items)

		items.push({
			label: report.title,
			route: {
				name: "Report",
				params: {
					module: route.params.module,
					id: route.params.id,
				},
			},
		})
	}

	return breadcrumbs
}
