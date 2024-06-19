import { Resource } from "./frappeUI"

export interface Session {
	login: Resource
	logout: Resource
	user: string | null
	isLoggedIn: boolean
}

export type SearchLinkOption = {
	value: string
	description: string
}

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

export interface ModuleSidebarLink {
	type: "Link" | "Section Break" | "Spacer"
	name: string
	label: string
	icon: string
	link_type: "DocType" | "Page" | "Report" | "Dashboard" | "URL"
	link_to: string
	route_to?: Route
	workspace?: string
	links?: ModuleSidebarLink[]
	url?: string
	opened?: boolean
	index?: number
}

export interface ModuleSidebar {
	name: string
	module: string
	module_home?: Route
	workspaces: ModuleSidebarLink[]
	sections: ModuleSidebarLink[]
}
