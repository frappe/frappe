// The email a reply answers, quoted as desk v1 quotes it: an "On … wrote:" line over its plain text.
import type { EmailActivity } from "@framework/ui/ActivityTimeline";
import { dayjsLocal } from "frappe-ui";
import { __ } from "@/i18n";

// Desk v1's clip, so a long thread does not bloat every reply.
const LIMIT = 20 * 1024;

/** Built as text nodes, so nothing from the email reaches the editor as markup. */
export function quoteEmail(email: EmailActivity["data"], timestamp?: string): string {
	const doc = document.implementation.createHTMLDocument("");
	const line = doc.createElement("p");
	line.textContent = attribution(email.sender, timestamp);
	const text = doc.createElement("p");
	plainText(email.content ?? "")
		.slice(0, LIMIT)
		.split("\n")
		.forEach((part, index) => {
			if (index) text.append(doc.createElement("br"));
			text.append(part);
		});
	doc.body.append(line, text);
	return doc.body.innerHTML;
}

// A row just sent has no time until the feed's echo brings it.
function attribution(sender: string, timestamp?: string) {
	if (!timestamp) return __("{0} wrote:", [sender]);
	const date = dayjsLocal(timestamp).format("Do MMMM YYYY, hh:mm A");
	return __("On {0}, {1} wrote:", [date, sender]);
}

// Desk v1's html2text: block ends and breaks become newlines, and at most one blank line survives.
function plainText(html: string) {
	const marked = html.replace(/<\/(div|p)>/gi, "<br></$1>").replace(/<br\s*\/?>/gi, "\n");
	const doc = new DOMParser().parseFromString(marked, "text/html");
	doc.querySelectorAll("style, script").forEach((node) => node.remove());
	return (doc.body.textContent ?? "").replace(/\n{3,}/g, "\n\n").trim();
}
