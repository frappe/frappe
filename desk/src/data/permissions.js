import { createResource } from "frappe-ui"
import { reactive } from "vue"

import { slug } from "@/utils/routing"

export const modulesBySlug = reactive({})
export const workspacesBySlug = reactive({})
export const doctypesBySlug = reactive({})

export const permissionsResource = createResource({
	url: "frappe.api.desk.get_permissions_for_current_user",
	transform(data) {
		data.allow_modules.forEach((module) => (modulesBySlug[slug(module)] = module))
		data.allow_workspaces.forEach((workspace) => (workspacesBySlug[slug(workspace)] = workspace))
		data.can_read.forEach((doctype) => (doctypesBySlug[slug(doctype)] = doctype))
		return data
	},
})

export default {
	permissionsResource,
	modulesBySlug,
	doctypesBySlug,
	workspacesBySlug,
}
