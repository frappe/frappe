export interface StudioApp {
	creation: string
	name: string
	modified: string
	owner: string
	modified_by: string
	docstatus: 0 | 1 | 2
	idx?: number
	/**	App Name : Data	*/
	app_name: string
	/**	App Title : Data */
	app_title: string
	/**	Route : Data */
	route: string
	/**	App Home : Link to the Studio Page */
	app_home: string
}

export type NewStudioApp = Pick<StudioApp, "app_title" | "route">