import type { ComponentProp, Operators } from "@/runtime/types"

export type * from "@/runtime/types"

export type EditingMode = "page" | "fragment" | "component"
export type StudioMode = "select" | "container"

export interface SlotConfig {
	slotName: string
	componentId: string
	// componentId:slotName
	slotId: string
}

export interface ContextMenuOption {
	label: string
	action?: CallableFunction
	condition?: () => boolean
	disabled?: () => boolean
	icon?: any
	theme?: "gray" | "red"
	// when present, the option expands into a nested (grouped) submenu on hover
	submenu?: ContextMenuGroup[]
}

export interface ContextMenuGroup {
	label?: string
	options: ContextMenuOption[]
}

export type ComponentProps = Record<string, ComponentProp>

export type Fieldtype =
	| "Check"
	| "Link"
	| "Float"
	| "Int"
	| "Select"
	| "Data"
	| "Long Text"
	| "Small Text"
	| "Text Editor"
	| "Text"
	| "JSON"
	| "Code"
export type DocTypeField = {
	fieldname: string
	fieldtype: Fieldtype
	label: string
	is_virtual?: boolean
	options?: string
	value?: any
	reqd: number
	read_only: number
	description?: string
}

export type Filter = {
	fieldname: string
	operator: Operators
	// in / not in carry a list of values; everything else a scalar
	value?: string | string[] | number | null
	field: DocTypeField
}

export type LeftPanelOptions = "Pages" | "Add Component" | "Layers" | "Data" | "Code" | "AI Assistant"
export type RightPanelOptions = "Properties" | "Styles" | "Events"
export type leftPanelComponentTabOptions = "Standard" | "Custom"
export type SettingsTab = "app" | "pages" | "ai"

// right panel
export type HashString = `#${string}`

export type RGBString = `rgb(${number}, ${number}, ${number})`
