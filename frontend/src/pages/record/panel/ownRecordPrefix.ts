// A server message may open with the record it names ("Task TASK-1: 'Title' (...)"); under a row
// of that record the prefix only repeats the page, so the row drops it.
const ESCAPES: [RegExp, string][] = [
	[/&/g, "&amp;"],
	[/</g, "&lt;"],
	[/>/g, "&gt;"],
	[/"/g, "&quot;"],
	[/'/g, "&#39;"],
];

function escaped(text: string) {
	return ESCAPES.reduce((out, [pattern, entity]) => out.replace(pattern, entity), text);
}

/** `message` without a leading "<doctype> <name>: " that names this record; any other text is kept. The server writes the doctype in the user's language, so `doctypes` lists each spelling. */
export function withoutOwnRecordPrefix(message: string, doctypes: (string | undefined)[], name?: string) {
	if (!name) return message;
	const prefixes = doctypes.flatMap((doctype) =>
		doctype ? [`${doctype} ${name}: `, `${escaped(doctype)} ${escaped(name)}: `] : []
	);
	const prefix = prefixes.find((one) => message.startsWith(one));
	return prefix && message.length > prefix.length ? message.slice(prefix.length) : message;
}
