type StyleValue = string | number | null | undefined

interface BlockStyleMap {
	[key: string]: StyleValue
}

interface BlockOptions {
	componentId?: string
	componentName: string
	children?: Array<BlockOptions>
	baseStyles?: BlockStyleMap
	mobileStyles?: BlockStyleMap
	tabletStyles?: BlockStyleMap
	[key: string]: any
}

interface Breakpoint {
	icon: string;
	device: string;
	displayName: string;
	width: number;
	visible: boolean;
}

interface CanvasProps {
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

interface ContextMenuOption {
	label: string
	action: CallableFunction
	condition?: () => boolean
}

interface ComponentProps {
	[key: string]: {
		type: string,
		default: string,
		inputType: string
	}
}
interface StudioPage {
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