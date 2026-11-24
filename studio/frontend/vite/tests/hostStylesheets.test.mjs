import assert from "node:assert/strict"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import test from "node:test"
import { build } from "vite"
import hostStylesheets from "../hostStylesheets.js"

const STYLESHEET =
	":root { --ink: black; background-color: white } html, body { margin: 0 } .card { color: var(--ink); background: white }"

test("each stylesheet gets a .host.css copy retargeted at :host", async () => {
	const root = fs.mkdtempSync(path.join(os.tmpdir(), "studio-host-stylesheets-"))
	try {
		fs.writeFileSync(path.join(root, "app.css"), STYLESHEET)
		fs.writeFileSync(path.join(root, "lazy.css"), ".button { color: red }")
		fs.writeFileSync(path.join(root, "lazy.js"), 'import "./lazy.css"; export default 1')
		fs.writeFileSync(
			path.join(root, "app.js"),
			'import "./app.css"; export const load = () => import("./lazy.js")',
		)
		const result = await build({
			configFile: false,
			root,
			logLevel: "silent",
			plugins: [hostStylesheets()],
			build: {
				write: false,
				manifest: true,
				cssCodeSplit: false,
				rolldownOptions: { input: path.join(root, "app.js"), preserveEntrySignatures: "exports-only" },
			},
		})
		const assets = Object.fromEntries(
			result.output
				.filter((output) => output.type === "asset")
				.map((output) => [output.fileName, String(output.source)]),
		)
		const document = Object.keys(assets).find((name) => name.endsWith(".css") && !name.endsWith(".host.css"))
		const host = assets[document.replace(/\.css$/, ".host.css")]

		assert.match(assets[document], /:root/)
		assert.doesNotMatch(host, /:root|html|body/)
		assert.match(host, /:host\s*\{\s*--ink/)
		assert.doesNotMatch(host, /:host\s*\{[^}]*background/)
		assert.match(host, /\.card\s*\{[^}]*background/)
		assert.match(host, /\.button/)
		assert.equal(Object.keys(assets).filter((name) => name.endsWith(".css")).length, 2)
		for (const chunk of result.output.filter((output) => output.type === "chunk")) {
			assert.equal(chunk.code.includes(document), false)
			assert.equal(chunk.code.includes(document.replace(/\.css$/, ".host.css")), false)
		}
		const manifest = JSON.parse(assets[".vite/manifest.json"])
		assert.equal(manifest["style.css"].file, document)
	} finally {
		fs.rmSync(root, { recursive: true, force: true })
	}
})
