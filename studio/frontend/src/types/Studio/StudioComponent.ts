export interface StudioComponent {
	name: string
	component_id: string
	component_name: string
	/** The app that owns the component. A component without an app is available in every app. */
	studio_app?: string | null
	/** The Frappe app that holds a global component in its files. */
	frappe_app?: string | null
	/**	Block : JSON	*/
	block?: any
	script?: string | null
	inputs?: StudioComponentInput[]
	creation?: string
	modified?: string
}

export interface StudioComponentInput {
	input_name: string
	/** The control that edits the value: the one in `control`, or else the first control of `prop_type`. */
	type: string
	/** The Vue type of a script prop, such as "String" or "Array". "Any" for a prop without a type. */
	prop_type?: string
	/** The control that the script names in `meta.control`. Empty when the script names none. */
	control?: string
	description?: string
	/** Text, or the value of a number or checkbox control in the editor's form. */
	default?: string | number | boolean
	required?: number
	options?: string // For select type
}
