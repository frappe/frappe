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
