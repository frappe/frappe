import type { FunctionalComponent } from "vue"
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
	originalElement?: string
	children?: Array<Block | BlockOptions>
	baseStyles?: BlockStyleMap
	rawStyles?: BlockStyleMap
	mobileStyles?: BlockStyleMap
	tabletStyles?: BlockStyleMap
	blockName?: string
	parentBlock?: Block | null
	classes?: string[]
	parentSlotName?: string // for top-level blocks inside a slot
	visibilityCondition?: string
	[key: string]: any
}

export type EditingMode = "page" | "fragment"
export type StudioMode = "select" | "container"

// slot
export interface Slot {
	slotId: string,
	slotName: string,
	slotContent: string | Block[],
	parentBlockId: string
}

export interface SlotConfig {
	slotName: string,
	componentId: string,
	// componentId:slotName
	slotId: string
}

export interface ContextMenuOption {
	label: string
	action: CallableFunction
	condition?: () => boolean
	disabled?: () => boolean
}

export type ComponentProp = {
	type: string
	default: VuePropDefault
	inputType: string
	modelValue?: any
	required?: boolean
	options?: Array<SelectOption> | Array<string>
}

export type ComponentProps = Record<string, ComponentProp>

// controls
export type SelectOption = { value: string, label: string }

// dynamic data
export type ExpressionEvaluationContext = Record<string, any> | undefined

export interface FrappeUIComponent {
	name: string,
	title: string,
	icon: string | FunctionalComponent,
	initialState?: Record<string, any>,
	initialSlots?: Array<string>,
	props?: Array<Record<string, any>>,
	emits?: Array<string> | Record<string, any>,
	editInFragmentMode?: boolean, // whether to open a separate canvas for editing this component
	proxyComponent?: any, // pseudo-component to be used in edit mode
}

export interface FrappeUIComponents {
	[key: string]: FrappeUIComponent
}

export type Fieldtype = "Check" | "Link" | "Float" | "Int" | "Select" | "Data" | "Long Text" | "Small Text" | "Text Editor" | "Text" | "JSON" | "Code"
export type DocTypeField = {
	fieldname: string
	fieldtype: Fieldtype
	label: string
	is_virtual?: boolean
	options?: string
	value?: any
}
export type Operators = "=" | "!=" | ">" | "<" | ">=" | "<=" | "like" | "not like" | "in" | "not in" | "between" | "not between" | "is" | "is not"

export type Filter = {
	fieldname: string
	operator: Operators
	value: string
	field: DocTypeField
}

export type LeftPanelOptions = "Pages" | "Add Component" | "Layers" | "Data" | "Code"
export type RightPanelOptions = "Properties" | "Events" | "Styles"

// right panel
export type HashString = `#${string}`

export type RGBString = `rgb(${number}, ${number}, ${number})`

// repeater
export type RepeaterContext = {
	dataItem: Record<string, any>
	dataIndex: number
	dataKey?: string
}

// completions
export type CompletionSource = {
	item: any,
	completion: Completion
}