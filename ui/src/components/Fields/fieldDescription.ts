import { sanitizeHtml } from "../../utils/sanitize";

// Customize Form lets a System Manager set any description, so it is not trusted markup.
// A `<style>` would restyle the page and a form could post off-site, as in `RichTextView`.
const CONFIG = { FORBID_TAGS: ["style", "form"], FORBID_ATTR: ["form", "formaction"] };

/** A field description as safe HTML for `v-html`. */
export function descriptionHtml(html: string | null | undefined): string {
	return sanitizeHtml(html, CONFIG);
}

/** A field description's text, for a control that can only draw a string. */
export function descriptionText(html: string | null | undefined): string | undefined {
	if (!html || !/[<&]/.test(html)) return html || undefined;
	const doc = new DOMParser().parseFromString(html.replace(/<br\s*\/?>/gi, " "), "text/html");
	return doc.body.textContent?.replace(/\s+/g, " ").trim() || undefined;
}
