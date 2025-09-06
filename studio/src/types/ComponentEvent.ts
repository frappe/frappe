import type { Component } from "vue"

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
	// on success for 'Call API' and 'Insert a Document'
	on_success: "message" | "script",
	success_message?: string
	on_success_script?: string,
	on_error: "message" | "script",
	// on error for 'Call API' and 'Insert a Document'
	error_message?: string,
	on_error_script?: string,
	/** action = 'Run Script' */
	script?: string
	// for editing
	isEditing?: boolean
	oldEvent?: Events | string
}

export type ActionConfiguration = {
	component: Component
	getProps: () => object
	events: Record<string, (event: any) => void>
	class?: string | string[]
}

export type ActionConfigurations = {
	[key in Actions]: ActionConfiguration[]
}
