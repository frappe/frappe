export interface Resource {
	url: string
	data: any
	loading: boolean
	fetched: boolean
	fetch: () => Promise<any>
	reset: () => Promise<any>
	reload: () => Promise<any>
	submit: (args?: any) => Promise<any>
	transform: (data: any) => any
	promise: Promise<any>
	error: string | null
}

export type AutocompleteValue = {
	value: string
	label: string
}
