export interface StudioComponent {
	name: string
	component_id: string
	component_name: string
	/** The app that owns the component. A component without an app is available in every app. */
	studio_app?: string | null
	/**	Block : JSON	*/
	block?: any
	script?: string | null
	inputs?: StudioComponentInput[]
	creation?: string
	modified?: string
}

export interface StudioComponentInput {
	input_name: string
	type: string
	description?: string
	/** Text, or the value of a number or checkbox control in the editor's form. */
	default?: string | number | boolean
	required?: number
	options?: string // For select type
}

// for UI
export interface ComponentInput {
	input_name: string
	type: string
	description?: string
	default?: string | number | boolean
	options?: string // For select type
	required?: number
	showPopover?: boolean
	inputControl?: any
	inputType?: string
}