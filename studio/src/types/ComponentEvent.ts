import type { DefineComponent } from "vue"

export type Events = 'click' | 'change' | 'focus' | 'blur' | 'submit' | 'keydown' | 'keyup' | 'keypress'

export type Actions = 'Call API' | 'Switch App Page' | 'Open Webpage' | 'Insert a Document' | 'Run Script'

export type Field = {
	field: string
	value: string
	name: string
}

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
	fields?: Array<Field>
	success_message?: string | null
	error_message?: string | null
	/** action = 'Run Script' */
	script?: string
	// for editing
	isEditing?: boolean
	oldEvent?: Events | string
}

export type ActionConfiguration = {
	component: DefineComponent
	getProps: () => object
	events: Record<string, (event: any) => void>
	class?: string | string[]
}

export type ActionConfigurations = {
	[key in Actions]: ActionConfiguration[]
}
