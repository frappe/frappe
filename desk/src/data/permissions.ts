import { createResource } from "frappe-ui"
import { reactive } from "vue"

import { slug } from "@/utils/routing"
import { Resource } from "@/types/frappeUI"
import { DocType, DocTypeMap, Report, ReportMap, Workspace, WorkspaceMap } from "@/types"

export const modulesBySlug = reactive({} as Record<string, string>)
export const workspacesBySlug = reactive({} as WorkspaceMap)
export const doctypesBySlug = reactive({} as DocTypeMap)
export const reportsBySlug = reactive({} as ReportMap)

export const permissionsResource: Resource = createResource({
	url: "frappe.api.desk.get_permissions_for_current_user",
	transform(data: Record<string, any>) {
		data.allow_modules.forEach((module: string) => {
			modulesBySlug[slug(module)] = module
		})
		data.allow_workspaces.forEach((workspace: Workspace) => {
			workspacesBySlug[slug(workspace.name)] = workspace
		})
		if (typeof data.doctype_map === "object") {
			;(Object.values(data.doctype_map) as DocType[]).forEach((doctype: DocType) => {
				doctypesBySlug[slug(doctype.name)] = doctype
			})
		}
		if (typeof data.all_reports === "object") {
			;(Object.values(data.all_reports) as Report[]).forEach((report: Report) => {
				reportsBySlug[slug(report.title)] = report
			})
		}
		return data
	},
})
