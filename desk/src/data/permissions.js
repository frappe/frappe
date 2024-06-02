import { createResource } from "frappe-ui"
import { reactive } from "vue"

import { slug } from "@/utils/routing"

export const modulesBySlug = reactive({})
export const workspacesBySlug = reactive({})
export const doctypesBySlug = reactive({})
export const reportsBySlug = reactive({})

export const permissionsResource = createResource({
	url: "frappe.api.desk.get_permissions_for_current_user",
	transform(data) {
		data.allow_modules.forEach((module) => (modulesBySlug[slug(module)] = module))
		data.allow_workspaces.forEach(
			(workspace) => (workspacesBySlug[slug(workspace.name)] = workspace)
		)
		Object.values(data.doctype_map).forEach((doctype) => {
			doctypesBySlug[slug(doctype.name)] = doctype
		})
		Object.values(data.all_reports).forEach((report) => {
			reportsBySlug[slug(report.title)] = report
		})
		return data
	},
})
