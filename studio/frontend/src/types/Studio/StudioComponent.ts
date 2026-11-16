export interface StudioComponent {
	name: string
	component_id: string
	component_name: string
	/**	Block : JSON	*/
	block?: any
	inputs?: StudioComponentInput[]
	creation?: string
	modified?: string
}

export interface StudioComponentInput {
	input_name: string
	type: string
	description?: string
	default?: string
	required?: number
	options?: string // For select type
}

// for UI
export interface ComponentInput {
	input_name: string
	type: string
	description?: string
	default?: string
	options?: string // For select type
	required?: number
	showPopover?: boolean
	inputControl?: any
	inputType?: string
}