import { Resource } from "@/types/frappeUI"
import { FieldTypes as DocFieldType } from "./controls"

type QueryParamDict = Record<string, string | string[]>

type ListField = {
	key: string
	label: string
	type: DocFieldType
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
	fieldtype: DocFieldType
	operator: ListFilterOperator
	value: string
	options: string[]
}

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
	sort: [string, "ASC" | "DESC"]
	from_meta: boolean
	fields: ListField[]
	title_field: [string, string]
	views: SavedView[]
} & SavedView

type ListResource = Omit<Resource, "data"> & {
	data: ListRow[]
}

export {
	QueryParamDict,
	ListField,
	ListRow,
	ListColumn,
	ListFilter,
	ListFilterOperator,
	SavedView,
	ListConfiguration,
	ListResource,
	isValidFilterOperator,
}
