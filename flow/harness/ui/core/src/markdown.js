import DOMPurify from "dompurify"
import { marked } from "marked"

marked.setOptions({ gfm: true, breaks: false })

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
	if (node.tagName === "A") {
		node.setAttribute("target", "_blank")
		node.setAttribute("rel", "noopener noreferrer")
	}
})

export function renderMarkdown(text) {
	return DOMPurify.sanitize(marked.parse(text ?? ""), {
		USE_PROFILES: { html: true },
		FORBID_TAGS: ["style", "form", "input", "button"],
	})
}
