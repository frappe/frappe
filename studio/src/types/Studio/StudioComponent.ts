export interface StudioComponent {
	name: string
	component_id: string
	component_name: string
	/**	Blocks : JSON	*/
	blocks?: any
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
}

// for UI
export interface ComponentInput {
	name: string
	type: string
	description?: string
	default?: string
	options?: string[] // For select type
	showPopover?: boolean
	inputControl?: any
	inputType?: string
}