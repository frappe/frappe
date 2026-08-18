import type { Component, FunctionalComponent } from "vue"
import Block from "../utils/block"
import type { VuePropDefault } from "@/types/vue"
import type { Completion } from "@codemirror/autocomplete"

export type ObjectLiteral = Record<string, any>
export type StyleValue = string | number | null | undefined

export interface BlockStyleMap {
	[key: string]: StyleValue
}

export interface BlockOptions {
	componentId?: string
	componentName: string
	componentProps?: Record<string, any>
	componentSlots?: Record<string, Slot>
	componentEvents?: Record<string, any>
	attributes?: Record<string, any>
	originalElement?: string
	children?: Array<Block | BlockOptions>
	baseStyles?: BlockStyleMap
	mobileStyles?: BlockStyleMap
	tabletStyles?: BlockStyleMap
	blockName?: string // optional user-friendly name for the block
	parentBlock?: Block | null
	classes?: string[]
	parentSlotName?: string // for top-level blocks inside a slot
	visibilityCondition?: string
	isStudioComponent?: boolean
	isChildOfComponent?: string
	isCustomVueComponent?: boolean
	extendedFromComponent?: Block
	[key: string]: any
}

export type EditingMode = "page" | "fragment" | "component"
export type StudioMode = "select" | "container"

// slot
export interface Slot {
	slotId: string
	slotName: string
	slotContent: Block[]
	parentBlockId: string
}

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

export type ComponentProp = {
	type: string
	default?: VuePropDefault
	inputType: string
	editor?: Component // custom prop editor
	modelValue?: any
	required?: boolean
	props?: Record<string, any>
	options?: Array<SelectOption> | Array<string>
	condition?: (state: object | null | undefined) => boolean
	itemTypes?: Record<string, any>
}

export type ComponentProps = Record<string, ComponentProp>

// controls
export type SelectOption = { value: string; label: string }

// dynamic data
export type ExpressionEvaluationContext = Record<string, any> | undefined

export interface FrappeUIComponent {
	name: string
	title: string
	icon: string | FunctionalComponent
	initialState?: Record<string, any>
	initialSlots?: Array<string>
	props?: Array<Record<string, any>>
	emits?: Array<string> | Record<string, any>
	editInFragmentMode?: boolean // whether to open a separate canvas for editing this component
	proxyComponent?: any // pseudo-component to be used in edit mode
	additionalProps?: Record<string, any> // additional props to be shown in the properties panel that are not explicitly defined in the component
	overrideProps?: Record<string, ComponentProp & { props?: Record<string, any> }> // to override prop editors for specific props
	hideProps?: Array<string> // to hide specific props from the properties panel
	expandArrayProps?: boolean // whether to render array props optimally using ArrayInput instead of as Code
	blockTemplate?: string // to specify a block template to be used instead of a vue component when this component is dragged into the canvas
	isCustomVueComponent?: boolean // whether this is a dynamically registered custom Vue component
	isGroup?: boolean // marks a family's root, a stacked tile that drops a whole working block template (e.g. List, SettingsDialog)
	group?: string // name of the family primary this component is a part of
	isStandalone?: boolean // false = can't mount outside its family root
	onSelect?: (block: Block) => void // editor hook — runs when a block of this component is selected on canvas/layers
}

export interface FrappeUIComponents {
	[key: string]: FrappeUIComponent
}

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
export type Operators =
	| "="
	| "!="
	| ">"
	| "<"
	| ">="
	| "<="
	| "like"
	| "not like"
	| "in"
	| "not in"
	| "between"
	| "not between"
	| "is"
	| "is not"

export type Filter = {
	fieldname: string
	operator: Operators
	// in / not in carry a list of values; everything else a scalar
	value?: string | string[] | number | null
	field: DocTypeField
}

export type LeftPanelOptions = "Pages" | "Add Component" | "Layers" | "Data" | "Code" | "AI Assistant"
export type RightPanelOptions = "Properties" | "Styles" | "Events" | "Interface"
export type leftPanelComponentTabOptions = "Standard" | "Custom"

// right panel
export type HashString = `#${string}`

export type RGBString = `rgb(${number}, ${number}, ${number})`

// scoped slots
export type SlotScope = Record<string, any>

// completions
export type CompletionSource = {
	item: any
	completion: Completion
}
