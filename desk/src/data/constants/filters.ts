import { FilterOperatorOption } from "@/types/list"
import { SelectOption } from "@/types/controls"

const numberTypes = ["Float", "Int", "Currency", "Percent"]
const dateTypes = ["Date", "Datetime"]
const linkTypes = ["Link", "Dynamic Link"]
const stringTypes = ["Data", "Long Text", "Small Text", "Text Editor", "Text"]

const filterOptions: Record<string, SelectOption[]> = {
	timespan: [
		{
			label: "Last Week",
			value: "last week",
		},
		{
			label: "Last Month",
			value: "last month",
		},
		{
			label: "Last Quarter",
			value: "last quarter",
		},
		{
			label: "Last 6 Months",
			value: "last 6 months",
		},
		{
			label: "Last Year",
			value: "last year",
		},
		{
			label: "Yesterday",
			value: "yesterday",
		},
		{
			label: "Today",
			value: "today",
		},
		{
			label: "Tomorrow",
			value: "tomorrow",
		},
		{
			label: "This Week",
			value: "this week",
		},
		{
			label: "This Month",
			value: "this month",
		},
		{
			label: "This Quarter",
			value: "this quarter",
		},
		{
			label: "This Year",
			value: "this year",
		},
		{
			label: "Next Week",
			value: "next week",
		},
		{
			label: "Next Month",
			value: "next month",
		},
		{
			label: "Next Quarter",
			value: "next quarter",
		},
		{
			label: "Next 6 Months",
			value: "next 6 months",
		},
		{
			label: "Next Year",
			value: "next year",
		},
	],
	check: [
		{
			label: "Yes",
			value: "true",
		},
		{
			label: "No",
			value: "false",
		},
	],
	is: [
		{
			label: "Set",
			value: "set",
		},
		{
			label: "Not Set",
			value: "not set",
		},
	],
}

const filterOperators: Record<string, FilterOperatorOption[]> = {
	string: [
		{ label: "Equals", value: "=" },
		{ label: "Not Equals", value: "!=" },
		{ label: "Like", value: "like" },
		{ label: "Not Like", value: "not like" },
		{ label: "In", value: "in" },
		{ label: "Not In", value: "not in" },
		{ label: "Is", value: "is" },
	],
	number: [
		{ label: "Equals", value: "=" },
		{ label: "Not Equals", value: "!=" },
		{ label: "Like", value: "like" },
		{ label: "Not Like", value: "not like" },
		{ label: "In", value: "in" },
		{ label: "Not In", value: "not in" },
		{ label: "Is", value: "is" },
		{ label: "<", value: "<" },
		{ label: ">", value: ">" },
		{ label: "<=", value: "<=" },
		{ label: ">=", value: ">=" },
	],
	select: [
		{ label: "Equals", value: "=" },
		{ label: "Not Equals", value: "!=" },
		{ label: "In", value: "in" },
		{ label: "Not In", value: "not in" },
		{ label: "Is", value: "is" },
	],
	link: [
		{ label: "Equals", value: "=" },
		{ label: "Not Equals", value: "!=" },
		{ label: "Like", value: "like" },
		{ label: "Not Like", value: "not like" },
		{ label: "In", value: "in" },
		{ label: "Not In", value: "not in" },
		{ label: "Is", value: "is" },
	],
	check: [
		{ label: "Equals", value: "=" },
		{ label: "Not Equals", value: "!=" },
	],
	date: [
		{ label: "Equals", value: "=" },
		{ label: ">", value: ">" },
		{ label: "<", value: "<" },
		{ label: ">=", value: ">=" },
		{ label: "<=", value: "<=" },
		{ label: "Between", value: "between" },
		{ label: "Timespan", value: "timespan" },
	],
	duration: [
		{ label: "Like", value: "like" },
		{ label: "Not Like", value: "not like" },
		{ label: "In", value: "in" },
		{ label: "Not In", value: "not in" },
		{ label: "Is", value: "is" },
	],
}

export { numberTypes, dateTypes, linkTypes, stringTypes, filterOptions, filterOperators }
