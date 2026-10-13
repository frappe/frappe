import DOMPurify from "dompurify"
import hljs from "highlight.js/lib/common"
import { marked, Renderer } from "marked"

marked.setOptions({ gfm: true, breaks: false })

marked.use({
	renderer: {
		table(token) {
			let html = Renderer.prototype.table.call(this, token)
			// a header-less table arrives as `| | |`: skip the empty strip
			if (token.header.every((cell) => !cell.text.trim())) html = html.replace(/<thead>[\s\S]*?<\/thead>\n?/, "")
			// a table segment's wrapper is drawn by MarkdownContent
			return token.segment ? html : `<div class="flow-md-table">${html}</div>\n`
		},
	},
})

// only the renderer's own class: the model's could pull in the app's styles (a fixed overlay)
DOMPurify.addHook("uponSanitizeAttribute", (node, data) => {
	if (data.attrName === "class") data.keepAttr = data.attrValue === "flow-md-table"
})

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
	// an image loads as soon as it renders, sending whatever its URL carries: it becomes a link
	const src = node.tagName === "IMG" ? node.getAttribute("src") : null
	if (src && !/^data:/i.test(src)) {
		const label = node.getAttribute("alt") || src
		// links don't nest: inside one, the image leaves just its label
		if (node.closest("a")) return node.replaceWith(label)
		const link = node.ownerDocument.createElement("a")
		link.setAttribute("href", src)
		link.textContent = label
		node.replaceWith(link)
		node = link
	}
	if (node.tagName === "A") {
		node.setAttribute("target", "_blank")
		node.setAttribute("rel", "noopener noreferrer")
	}
})

// model text can carry injected HTML: nothing in it may restyle the page or fetch on render
function sanitize(html) {
	return DOMPurify.sanitize(html, {
		USE_PROFILES: { html: true },
		FORBID_TAGS: ["style", "form", "input", "button", "video", "audio", "source", "track", "picture"],
		FORBID_ATTR: ["style", "srcset", "background"],
	})
}

export function renderMarkdown(text) {
	return sanitize(marked.parse(text ?? ""))
}

// Markdown split at top-level code blocks, so each one can render as a real
// component (header, copy button, highlighting) instead of raw HTML:
//   {type: "html", html}          sanitized rendered markdown
//   {type: "code", code, lang}    fenced or indented code block
//   {type: "table", html}         table without its scroll wrapper
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
		} else if (token.type === "table") {
			flush()
			segments.push({ type: "table", html: sanitize(marked.parser([{ ...token, segment: true }])) })
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
