let has_words = function (list, item) {
	if (!item) return true
	if (!list) return false
	for (var i = 0, j = list.length; i < j; i++) {
		if (item.indexOf(list[i]) != -1) return true
	}
	return false
}

export function guess_colour(text, default_style, _colour) {
	var style = default_style || "default"
	var colour = "gray"
	if (text) {
		text = String(text)
		if (has_words(["Pending", "Review", "Medium", "Not Approved"], text)) {
			style = "warning"
			colour = "orange"
		} else if (has_words(["Open", "Urgent", "High", "Failed", "Rejected", "Error"], text)) {
			style = "danger"
			colour = "red"
		} else if (
			has_words(
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
			)
		) {
			style = "success"
			colour = "green"
		} else if (has_words(["Submitted"], text)) {
			style = "info"
			colour = "blue"
		}
	}
	return colour
}
