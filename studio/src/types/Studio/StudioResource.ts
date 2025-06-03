export type ResourceType = "API Resource" | "Document List" | "Document"
export type Filters = Record<string, string | string[]>

interface BaseResource {
	/**	Child Table record name linked to page */
	name?: string
	resource_child_table_id?: string
	/**	Resource ID */
	resource_id: string
	/**	Resource Name */
	resource_name: string
	resource_type: ResourceType
	transform_results?: boolean
	transform?: string
	/** for Whitelisted methods */
	[key: string]: any
}

export interface DocumentResource extends BaseResource {
	resource_type: "Document"
	document_type: string
	document_name?: string
	whitelisted_methods?: string[]
	fetch_document_using_filters?: boolean
	filters?: Filters
}

export interface DocumentListResource extends BaseResource {
	resource_type: "Document List"
	document_type: string
	fields?: string[]
	filters?: Filters
	limit?: number
}

export interface APIResource extends BaseResource {
	resource_type: "API Resource"
	url: string
	method: "GET" | "POST" | "PUT" | "DELETE"
	filters?: Filters
}

export type Resource = DocumentResource | DocumentListResource | APIResource

export type NewResource = Omit<Resource, "resource_child_table_id"> & {
	source: "New Data Source" | "Existing Data Source"
	[key: string]: any
}


// result
export type DocumentResult = Record<string, any>
export type DataResult = Array<Record<string, any>>