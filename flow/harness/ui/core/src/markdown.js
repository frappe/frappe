import DOMPurify from "dompurify"
import hljs from "highlight.js/lib/common"
import { marked } from "marked"

marked.setOptions({ gfm: true, breaks: false })

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
	if (node.tagName === "A") {
		node.setAttribute("target", "_blank")
		node.setAttribute("rel", "noopener noreferrer")
	}
})

function sanitize(html) {
	return DOMPurify.sanitize(html, {
		USE_PROFILES: { html: true },
		FORBID_TAGS: ["style", "form", "input", "button"],
	})
}

export function renderMarkdown(text) {
	return sanitize(marked.parse(text ?? ""))
}

// Markdown split at top-level code blocks, so each one can render as a real
// component (header, copy button, highlighting) instead of raw HTML:
//   {type: "html", html}          sanitized rendered markdown
//   {type: "code", code, lang}    fenced or indented code block
export function renderMarkdownSegments(text) {
	const tokens = marked.lexer(text ?? "")
	const segments = []
	let pending = []
	const flush = () => {
		if (!pending.length) return
		const html = sanitize(marked.parser(pending))
		pending = []
		// blank-line tokens between code blocks render as whitespace-only chunks
		if (html.trim()) segments.push({ type: "html", html })
	}
	for (const token of tokens) {
		if (token.type === "code") {
			flush()
			segments.push({ type: "code", code: token.text, lang: token.lang?.split(/\s+/)[0] || null })
		} else {
			pending.push(token)
		}
	}
	flush()
	return segments
}

function escapeHtml(code) {
	return code.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c])
}

// hljs escapes the source itself, so the returned HTML is v-html safe.
export function highlightCode(code, lang) {
	if (lang && hljs.getLanguage(lang)) {
		try {
			return hljs.highlight(code, { language: lang }).value
		} catch {
			// unregistered grammar edge case — fall through to plain text
		}
	}
	return escapeHtml(code)
}
