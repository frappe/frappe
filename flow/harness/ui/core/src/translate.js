// The translations of the page around the chat when it keeps a list of them (Desk's, or the one
// /flow and apps put on the window under either name), else the English as written. The `{0}`
// placeholders are filled here: a page's own translate function is never called, since apps take
// arguments differently.
export function __(message, args, context) {
	const messages =
		globalThis.frappe?._messages ?? globalThis.translatedMessages ?? globalThis.translated_messages
	const text = (context && messages?.[`${message}:${context}`]) || messages?.[message] || message
	return args ? text.replace(/\{(\d+)\}/g, (match, index) => args[index] ?? match) : text
}
