import assert from "node:assert/strict"
import test from "node:test"

import { JSDOM } from "jsdom"

// DOMPurify binds its hooks to a window at import time, so the DOM has to exist
// before markdown.js is loaded — hence the dynamic import.
const dom = new JSDOM("")
globalThis.window = dom.window
globalThis.document = dom.window.document

const { renderMarkdown, renderMarkdownSegments } = await import("../src/markdown.js")

const TABLE = "| col | val |\n| --- | --- |\n| a | 1 |"

test("a table renders inside the scroll wrapper", () => {
	const html = renderMarkdown(TABLE)
	assert.match(html, /<div class="flow-md-table">\s*<table>/)
	assert.match(html, /<\/table>\s*<\/div>/)
	// one wrapper per table, not per row
	assert.equal(html.match(/flow-md-table/g).length, 1)
})

test("the segmented renderer wraps tables too", () => {
	const segments = renderMarkdownSegments(`intro\n\n${TABLE}\n\n\`\`\`js\ncode\n\`\`\``)
	assert.deepEqual(
		segments.map((segment) => segment.type),
		["html", "code"],
	)
	assert.ok(segments[0].html.includes('class="flow-md-table"'))
})
