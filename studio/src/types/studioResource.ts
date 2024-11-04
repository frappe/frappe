export type ResourceType = "API Resource" | "Document List" | "Document"
export type Filters = Record<string, string | string[]>

interface BaseResource {
	/**	Child Table record name linked to page */
	name: string
	/**	Child Table record name linked to page */
	docname: string
	/**	Resource Docname */
	resource_name: string
	resource_type: ResourceType
	transform_results?: boolean
	transform?: string
}

export interface DocumentResource extends BaseResource {
	resource_type: "Document"
	document_type: string
	document_name?: string
	whitelisted_methods?: string[]
	filters?: Filters
}

export interface DocumentListResource extends BaseResource {
	resource_type: "Document List"
	document_type: string
	fields?: string[]
	filters?: Filters
}

export interface APIResource extends BaseResource {
	resource_type: "API Resource"
	url: string
	method: "GET" | "POST" | "PUT" | "DELETE"
	filters?: Filters
}

export type Resource = DocumentResource | DocumentListResource | APIResource

export type NewResource = Omit<Resource, "name" | "docname"> & {
	source: "New Data Source" | "Existing Data Source"
	[key: string]: any
}


// result
export type DocumentResult = Record<string, any>
export type DataResult = Array<Record<string, any>>