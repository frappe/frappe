export interface StudioModuleMeta {
	module_name: string
	module_path: string
	frappe_app: string
	studio_app: string
	file_path: string
}

// A `Studio Module Import` child row attached to a Studio App or Studio Page
export interface StudioModuleImport {
	module_name?: string
	module_path: string
}
