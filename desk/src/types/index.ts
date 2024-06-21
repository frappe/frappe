import { Resource } from "./frappeUI"

export interface Session {
	login: Resource
	logout: Resource
	user: string | null
	isLoggedIn: boolean
}

// Routing
export type Route = {
	name: string
	params?: Record<string, string>
}

export interface Breadcrumb {
	label: string
	route: Route
}

export type Workspace = { name: string; module: string }
export type DocType = {
	name: string
	module: string
	issingle: boolean
	istable: boolean
	read_only: boolean
	restrict_to_domain: string
	in_create: boolean
}
export type Report = {
	ref_doctype: string
	report_type: string
	title: string
}
export interface WorkspaceMap {
	[key: string]: Workspace
}
export interface DocTypeMap {
	[key: string]: DocType
}
export interface ReportMap {
	[key: string]: Report
}

// Desktop
export interface DesktopItem {
	name: string
	label: string
	icon: string
	color: string
	link_type: string
	url: string
	module: string
	module_slug?: string
}

// Module Sidebar
export type ModuleSidebarItemType = "Link" | "Section Break" | "Spacer"
export type ModuleSidebarLinkType = "DocType" | "Page" | "Report" | "Dashboard" | "URL"
export type UpdateSidebarItemAction = "addBelow" | "edit" | "delete" | "duplicate"
export interface ModuleSidebarItem {
	type: ModuleSidebarItemType
	name: string
	label: string
	icon: string
	workspace?: string
	/** link_type for type = Link */
	link_type: ModuleSidebarLinkType
	link_to: string
	/** exact app route based on link_type & link_to */
	route_to?: Route
	/** section links for type = Section Break */
	links?: ModuleSidebarItem[]
	/** tracks if the section is opened for type = Section Break */
	opened?: boolean
	/** URL for link_type = URL */
	url?: string
	index?: number
}

export interface ModuleSidebar {
	name: string
	module: string
	module_home?: Route
	workspaces: ModuleSidebarItem[]
	sections: ModuleSidebarItem[]
}
