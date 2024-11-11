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
	/**	Page Name : Data	*/
	page_name: string
	/**	Published : Check	*/
	published?: 0 | 1
	/**	Route : Data	*/
	route: string
	/**	Blocks : JSON	*/
	blocks?: any
	/**	Draft Blocks : JSON	*/
	draft_blocks?: any
	/**	Title : Data	*/
	page_title?: string
	[key: string]: any
}