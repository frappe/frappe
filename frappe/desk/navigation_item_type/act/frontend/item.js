// The `Act` kind: a shell act the row runs when clicked. It opens no place, so it never goes active.
// Its payload is `{ act, value? }`; a payload with no `value` asks for one on click.

export default {
	icon: "zap",

	render(item) {
		const act = item.payload?.act;
		if (!act) return null;

		return "value" in item.payload ? { act, value: item.payload.value } : { act };
	},

	// The editor writes a label when it adds the row; this is the last fallback.
	label(item) {
		return item.payload?.act;
	},
};
