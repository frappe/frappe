import { BlockOptions } from "@/types"

/**
 * Expand a compact node (name/style/c/props...) into Studio block format
 * (componentName/baseStyles/children/componentProps...).
 * Mirrors BlockCodec.expand() in studio/ai/block_codec.py.
 */
export function expandBlock(node: Record<string, any>): BlockOptions {
	const block: BlockOptions = {
		componentName: node.name ?? "container",
		baseStyles: node.style ?? {},
		rawStyles: node.rstyle ?? {},
		componentProps: node.props ?? {},
		componentSlots: node.slots ?? {},
		mobileStyles: node.mstyle ?? {},
		tabletStyles: node.tstyle ?? {},
		children: Array.isArray(node.c) ? node.c.map(expandBlock) : [],
	}

	if (node.id) block.componentId = node.id
	if (node.originalElement) block.originalElement = node.originalElement
	if (node.label) block.blockName = node.label

	return block
}

/**
 * Try to parse a partial JSON stream buffer into a Studio block.
 * The buffer is usually incomplete mid-stream (unclosed strings/brackets), so we
 * best-effort repair it: close the open string, drop dangling trailing tokens, and
 * close open brackets. If that still fails we trim back one member and retry.
 */
export function tryParseJsonBlock(buffer: string): BlockOptions | null {
	const text = stripFences(buffer)
	if (!text) return null
	let parsed = parsePartialJson(text)
	if (Array.isArray(parsed)) parsed = parsed[0]
	if (!parsed || typeof parsed !== "object" || !("name" in parsed)) return null
	return expandBlock(parsed as Record<string, any>)
}

function stripFences(text: string): string {
	return text
		.trim()
		.replace(/^```(?:json|yaml)?\s*/i, "")
		.replace(/```\s*$/i, "")
		.trim()
}

function parsePartialJson(text: string): any {
	try {
		return JSON.parse(text)
	} catch {
		// fall through to repair
	}

	let working = escapeInnerQuotes(text)
	for (let attempt = 0; attempt < 8; attempt++) {
		const { candidate, trimmed } = repair(working)
		if (candidate) {
			try {
				return JSON.parse(candidate)
			} catch {
				// candidate didn't parse; retry on the trimmed buffer
			}
		}
		if (!trimmed || trimmed === working) return null
		working = trimmed
	}
	return null
}


/**
 * Escape stray double-quotes inside string values. A `"` only legitimately ends a
 * string when the next non-space char is structural (`,` `}` `]` `:` or EOF);
 * otherwise it's unescaped content (e.g. He said "hi") and we escape it.
 */
function escapeInnerQuotes(text: string): string {
	let out = ""
	let inString = false
	for (let i = 0; i < text.length; i++) {
		const ch = text[i]
		if (!inString) {
			out += ch
			if (ch === '"') inString = true
			continue
		}
		if (ch === "\\") {
			out += ch + (text[i + 1] ?? "")
			i++
			continue
		}
		if (ch === '"') {
			let j = i + 1
			while (j < text.length && /\s/.test(text[j])) j++
			const next = j < text.length ? text[j] : ""
			if (next === "" || ",}]:".includes(next)) {
				out += ch
				inString = false
			} else {
				out += '\\"'
			}
			continue
		}
		out += ch
	}
	return out
}

interface Repair {
	candidate: string // best guess at a complete, parseable JSON string
	trimmed: string // text with its last (incomplete) member removed, for retry
}

/**
 * Scan `text` once, then produce:
 *  - candidate: text with the open string closed, trailing comma/dangling key
 *    dropped, and all open brackets closed.
 *  - trimmed: text cut back to the last structural boundary (a top-of-container
 *    `,`, `{` or `[`), so a failed candidate can be retried minus one member.
 */
function repair(text: string): Repair {
	const closers: string[] = []
	let inString = false
	let escaped = false
	let lastBoundary = -1

	for (let i = 0; i < text.length; i++) {
		const ch = text[i]
		if (inString) {
			if (escaped) escaped = false
			else if (ch === "\\") escaped = true
			else if (ch === '"') inString = false
			continue
		}
		if (ch === '"') inString = true
		else if (ch === "{") {
			closers.push("}")
			lastBoundary = i
		} else if (ch === "[") {
			closers.push("]")
			lastBoundary = i
		} else if (ch === "}" || ch === "]") closers.pop()
		else if (ch === ",") lastBoundary = i
	}

	let candidate = inString ? text + '"' : text
	let prev = ""
	while (candidate !== prev) {
		prev = candidate
		candidate = candidate.replace(/\s+$/, "")
		if (candidate.endsWith(",")) {
			candidate = candidate.slice(0, -1)
		} else {
			// dangling `"key":` with no value yet
			const dangling = candidate.match(/,?\s*"(?:[^"\\]|\\.)*"\s*:$/)
			if (dangling) candidate = candidate.slice(0, candidate.length - dangling[0].length)
		}
	}
	for (let i = closers.length - 1; i >= 0; i--) candidate += closers[i]

	let trimmed = ""
	if (lastBoundary >= 0) {
		// keep an opening bracket (empty container is valid); drop a trailing comma
		trimmed = text[lastBoundary] === "," ? text.slice(0, lastBoundary) : text.slice(0, lastBoundary + 1)
	}

	return { candidate, trimmed }
}
