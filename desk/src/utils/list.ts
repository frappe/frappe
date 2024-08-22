import { RouteQuery, ListFilter } from "@/types/list"

const getFilterValue = (filter: ListFilter): string | boolean =>
	filter.fieldtype == "Check" ? filter.value == "true" : filter.value

export function getFilterQuery(filters: ListFilter[]): RouteQuery {
	const q: RouteQuery = {}
	filters.map((f) => {
		const { fieldname, operator } = f
		const value = getFilterValue(f)

		let query_value = q[fieldname]

		// No previous filters exist on the field
		// for equals operator, initialize query param as a string
		if (operator == "=" && !(fieldname in q)) {
			query_value = JSON.stringify(value)
		}
		// for other operators, initialize query param as a list
		else if (!(fieldname in q)) {
			query_value = [JSON.stringify([operator, value])]
		}

		// Previous filters exist on the field
		// if the query value is a list, append the new filter
		else if (Array.isArray(query_value)) {
			query_value.push(JSON.stringify([operator, value]))
		}
		// if the query value is a string (ie. previous operator was equals)
		// convert it to a list and append the new filter
		else {
			query_value = [query_value, JSON.stringify([operator, value])]
		}

		q[fieldname] = query_value
	})
	return q
}

const hasWords = (list: string[], item: string) => list.some((word: string) => item.includes(word))

const orangeStatus = ["Pending", "Review", "Medium", "Not Approved"]
const redStatus = ["Open", "Urgent", "High", "Failed", "Rejected", "Error"]
const greenStatus = [
	"Closed",
	"Finished",
	"Converted",
	"Completed",
	"Complete",
	"Confirmed",
	"Approved",
	"Yes",
	"Active",
	"Available",
	"Paid",
	"Success",
]

export function guessColour(text: string) {
	if (!text) return "gray"

	if (hasWords(orangeStatus, text)) return "orange"
	else if (hasWords(redStatus, text)) return "red"
	else if (hasWords(greenStatus, text)) return "green"
	else if (text == "Submitted") return "blue"
	else return "gray"
}
