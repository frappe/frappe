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
	componentEvents?: Record<string, any>
	children?: Array<BlockOptions>
	baseStyles?: BlockStyleMap
	mobileStyles?: BlockStyleMap
	tabletStyles?: BlockStyleMap
	blockName?: string
	parentBlock?: Block | null
	classes?: string[]
	[key: string]: any
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

export interface ComponentProps {
	[key: string]: {
		type: string,
		default: VuePropDefault,
		inputType: string
		modelValue?: any
	}
}

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
export type RightPanelOptions = "Props" | "Events" | "Styles"