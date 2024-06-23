const getFilterValue = (filter) =>
	filter.fieldtype == "Check" ? filter.value == "true" : filter.value

export function getFilterQuery(filters) {
	const q = {}
	filters.map((f) => {
		const { fieldname, operator } = f
		const value = getFilterValue(f)

		// No previous filters exist on the field
		// for equals operator, initialize query param as a string
		if (operator == "=" && !q[fieldname]) {
			q[fieldname] = JSON.stringify(value)
		}
		// for other operators, initialize query param as a list
		else if (!q[fieldname]) {
			q[fieldname] = [JSON.stringify([operator, value])]
		}

		// Previous filters exist on the field
		// if the query value is a list, append the new filter
		else if (Array.isArray(q[fieldname])) {
			q[fieldname].push(JSON.stringify([operator, value]))
		}
		// if the query value is a string (ie. previous operator was equals)
		// convert it to a list and append the new filter
		else {
			q[fieldname] = [q[fieldname], JSON.stringify([operator, value])]
		}
	})
	return q
}

const hasWords = (list, item) => list.some((word) => item.includes(word))

export function guessColour(text) {
	if (!text) return "gray"

	switch (text) {
		case hasWords(["Pending", "Review", "Medium", "Not Approved"], text):
			return "orange"
		case hasWords(["Open", "Urgent", "High", "Failed", "Rejected", "Error"], text):
			return "red"
		case hasWords(
			[
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
			],
			text
		):
			return "green"
		case text === "Submitted":
			return "blue"
		default:
			return "gray"
	}
}
