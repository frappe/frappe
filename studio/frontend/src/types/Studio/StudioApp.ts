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
	/**	Favicon : Attach Image */
	favicon?: string
	/**	Is Standard : Check */
	is_standard: 0 | 1
	/**	Frappe App : Target Frappe App for export */
	frappe_app?: string
	/**	Build Bundle on Publish : Check — a database app can be built with Vite instead of
	 * compiled in the browser */
	build_on_publish?: 0 | 1
}

export type NewStudioApp = Pick<StudioApp, "app_title" | "route" | "app_name"> & {
	app_name_placeholder?: string
}