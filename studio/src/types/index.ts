import Block from "../utils/block"
import { VuePropDefault } from "@/types/vue"

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
	children?: Array<BlockOptions>
	baseStyles?: BlockStyleMap
	mobileStyles?: BlockStyleMap
	tabletStyles?: BlockStyleMap
	blockName?: string
	parentBlock?: Block | null
	classes?: string[]
	parentSlotName?: string // for top-level blocks inside a slot
	[key: string]: any
}

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

export interface Breakpoint {
	icon: string;
	device: string;
	displayName: string;
	width: number;
	visible: boolean;
}

export interface CanvasProps {
	overlayElement: HTMLElement | null;
	background: string;
	scale: number;
	translateX: number;
	translateY: number;
	settingCanvas: boolean;
	scaling: boolean;
	panning: boolean;
	breakpoints: Breakpoint[];
}

export interface ContextMenuOption {
	label: string
	action: CallableFunction
	condition?: () => boolean
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
	icon: string,
	initialState?: Record<string, any>,
	props?: Array<Record<string, any>>,
	emits?: Array<string> | Record<string, any>,
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