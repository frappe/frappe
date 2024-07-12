import { Resource } from "@/types/frappeUI"
import { FieldTypes } from "./controls"

type RouteQuery = Record<string, string | string[]>

type ListField = {
	key: string
	label: string
	type: FieldTypes
	options: string[]
}

type ListColumn = { width: string } & ListField
type ListRow = Record<string, any>

const validOperators = [
	"=",
	"!=",
	"<",
	">",
	"<=",
	">=",
	"is",
	"like",
	"not like",
	"in",
	"not in",
	"between",
	"timespan",
] as const
type ListFilterOperator = (typeof validOperators)[number]

const isValidFilterOperator = (operator: any): operator is ListFilterOperator =>
	validOperators.includes(operator)

type ListFilter = {
	fieldname: string
	fieldtype: FieldTypes
	operator: ListFilterOperator
	value: string
	options: string[]
}
type ListQueryFilter = [string, ListFilterOperator, string | string[]]

type ListSort = [string, "ASC" | "DESC"]

type SavedView = {
	name: string
	label: string
	icon: string
}

type ListConfiguration = {
	document_type: string
	custom: boolean
	columns: ListColumn[]
	filters: ListFilter[]
	sort: ListSort
	from_meta: boolean
	fields: ListField[]
	title_field: [string, string]
	views: SavedView[]
} & SavedView

type ListResource = Omit<Resource, "data"> & {
	data: ListRow[]
}

type FilterOperatorOption = { label: string; value: ListFilterOperator }

export {
	RouteQuery,
	ListField,
	ListRow,
	ListColumn,
	ListFilterOperator,
	ListFilter,
	ListQueryFilter,
	ListSort,
	SavedView,
	ListConfiguration,
	ListResource,
	FilterOperatorOption,
	isValidFilterOperator,
}
