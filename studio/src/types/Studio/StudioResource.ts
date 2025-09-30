import type { Operators } from "@/types"
export type ResourceType = "API Resource" | "Document List" | "Document"
export type Filters = Record<string, [Operators, any]>

interface BaseResource {
	/**	Child Table record name = Resource ID */
	resource_id: string
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
	limit?: number | null
	sort_field?: string
	sort_order?: "asc" | "desc"
}

export interface APIResource extends BaseResource {
	resource_type: "API Resource"
	url: string
	method: "GET" | "POST" | "PUT" | "DELETE"
	filters?: Filters
	params?: Record<string, any>
}

export type Resource = DocumentResource | DocumentListResource | APIResource

// result
export type DocumentResult = Record<string, any>
export type DataResult = Array<Record<string, any>>