import Block from "../utils/block"

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
	}
}

export type VuePropType = {
	name: 'String' | 'Number' | 'Boolean' | 'Array' | 'Object' | 'Function'
	[key: string]: any
}

type VuePropDefaultType = string | number | boolean | undefined
type VuePropDefault = VuePropDefaultType | (() => VuePropDefaultType)

export type VueProp = {
	type: VuePropType | VuePropType[]
	default: VuePropDefault
	required: boolean
}

export interface StudioPage {
	creation: string
	name: string
	modified: string
	owner: string
	modified_by: string
	docstatus: 0 | 1 | 2
	parent?: string
	parentfield?: string
	parenttype?: string
	idx?: number
	/**	Published : Check	*/
	published?: 0 | 1
	/**	Page Name : Data	*/
	page_name?: string
	/**	Route : Data	*/
	route?: string
	/**	Blocks : JSON	*/
	blocks?: any
	/**	Draft Blocks : JSON	*/
	draft_blocks?: any
	/**	Title : Data	*/
	page_title?: string
}

export interface StudioApp {
	creation: string
	name: string
	modified: string
	owner: string
	modified_by: string
	docstatus: 0 | 1 | 2
	parent?: string
	parentfield?: string
	parenttype?: string
	idx?: number
	app_name?: string
	app_title?: string
	route?: string
}

// controls
export type SelectOption = { value: string, label: string }