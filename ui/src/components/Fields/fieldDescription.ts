import { sanitizeHtml } from "../../utils/sanitize";

// Customize Form lets a System Manager set any description, so it is not trusted markup.
// A `<style>` would restyle the page and a form could post off-site, as in `RichTextView`.
const CONFIG = {
	FORBID_TAGS: ["style", "form"],
	FORBID_ATTR: ["form", "formaction"],
	ADD_ATTR: ["target"],
};

/** A field description as safe HTML for `v-html`, each link opening in a new tab. */
export function descriptionHtml(html: string | null | undefined): string {
	return sanitizeHtml(withLinksInNewTab(html), CONFIG);
}

// A link must not take the user off the form or settings dialog they are editing. The sanitiser
// runs last, so what this builds is never trusted.
function withLinksInNewTab(html: string | null | undefined): string {
	if (!html || !/<a[\s>]/i.test(html)) return html || "";
	const template = document.createElement("template");
	template.innerHTML = html;
	for (const link of template.content.querySelectorAll("a[href]")) {
		link.setAttribute("target", "_blank");
		link.setAttribute("rel", "noopener noreferrer");
	}
	return template.innerHTML;
}

/** A field description's text, for a control that can only draw a string. */
export function descriptionText(html: string | null | undefined): string | undefined {
	if (!html || !/[<&]/.test(html)) return html || undefined;
	const doc = new DOMParser().parseFromString(html.replace(/<br\s*\/?>|<\/(p|li|div|pre|tr)>/gi, " "), "text/html");
	return doc.body.textContent?.replace(/\s+/g, " ").trim() || undefined;
}
