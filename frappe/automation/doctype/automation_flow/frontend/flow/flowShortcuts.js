const TEXT_FIELDS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

/** Ctrl or Cmd with S saves; with Z undoes, and with Shift redoes. Z in a field stays the field's own. */
export function handleShortcut(event, { save, undo, redo }) {
	if (!(event.ctrlKey || event.metaKey) || event.altKey) return;
	const key = event.key.toLowerCase();
	if (key === "s") {
		event.preventDefault();
		save();
		return;
	}
	if (key !== "z" || isTyping(event.target)) return;
	event.preventDefault();
	if (event.shiftKey) redo();
	else undo();
}

function isTyping(target) {
	return TEXT_FIELDS.has(target?.tagName) || Boolean(target?.isContentEditable);
}
