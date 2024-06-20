const getFilterValue = (filter) =>
	filter.fieldtype == "Check" ? filter.value == "true" : filter.value

export function getFilterQuery(filters) {
	const q = {}
	filters.map((f) => {
		const fieldname = f.fieldname
		const operator = f.operator
		const value = getFilterValue(f)
		if (operator == "=" && !q[fieldname]) {
			q[fieldname] = JSON.stringify(value)
		} else if (!q[fieldname]) {
			q[fieldname] = [JSON.stringify([operator, value])]
		} else if (q[fieldname].constructor === Array) {
			q[fieldname].push(JSON.stringify([operator, value]))
		} else {
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
