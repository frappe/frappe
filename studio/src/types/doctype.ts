export type FieldTypes =
	| "Data"
	| "Int"
	| "Float"
	| "Currency"
	| "Check"
	| "Text"
	| "Small Text"
	| "Long Text"
	| "Code"
	| "Text Editor"
	| "Date"
	| "Datetime"
	| "Time"
	| "HTML"
	| "Image"
	| "Attach"
	| "Select"
	| "Read Only"
	| "Section Break"
	| "Column Break"
	| "Table"
	| "Button"
	| "Link"
	| "Dynamic Link"
	| "Password"
	| "Signature"
	| "Color"
	| "Barcode"
	| "Geolocation"
	| "Duration"
	| "Percent"
	| "Rating"
	| "Icon"

// Grid
export interface GridColumn {
	label: string
	fieldname: string
	fieldtype: FieldTypes
	options?: string | string[]
	width?: number
	onChange?: (value: string, index: number) => void
}

export interface GridRow {
	name: string
	[fieldname: string]: string | number | boolean
}
