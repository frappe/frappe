/** `text` as the plain text an `ErrorMessage` shows: it reads its message as HTML. */
export function asErrorHtml(text: string): string {
	return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
