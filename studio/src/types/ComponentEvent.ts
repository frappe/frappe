import type { DefineComponent } from "vue"
import { GridRow } from "./doctype"

export type Events = 'click' | 'change' | 'focus' | 'blur' | 'submit' | 'keydown' | 'keyup' | 'keypress'

export type Actions = 'Call API' | 'Switch App Page' | 'Open Webpage' | 'Insert a Document'

export type ComponentEvent = {
	event: Events | string
	action: Actions
	/** action = 'Call API */
	api_endpoint?: string
	/** action = 'Switch App Page */
	page?: string
	/** action = 'Open Webpage' */
	url?: string
	/** action = 'Insert a Document' */
	doctype?: string
	fields?: Array<any>[]
	success_message?: string | null
	error_message?: string | null
}

export type ActionConfiguration = {
	component: DefineComponent
	getProps: () => object
	events: Record<string, (event: any) => void>
}

export type ActionConfigurations = {
	[key in Actions]: ActionConfiguration[]
}
