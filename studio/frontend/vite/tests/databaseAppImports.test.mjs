import assert from "node:assert/strict"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"
import { build } from "vite"
import databaseAppImports from "../databaseAppImports.js"
import sharedDependencyResolver from "../sharedDependencyResolver.js"
import studioRootAlias from "../studioRootAlias.js"

const frontend = fileURLToPath(new URL("../../", import.meta.url))
const CANARY = "STUDIO_DB_CANARY"
const outsideFiles = {
	"secret.json": JSON.stringify({ password: CANARY }),
	"secret.css": `:root { --secret: "${CANARY}" }`,
	"secret.txt": CANARY,
}

async function buildApp(files, databaseApp = true) {
	const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "studio-db-imports-"))
	const appFolder = path.join(tmp, "studio", "shop")
	try {
		for (const [folder, sources] of [
			[tmp, outsideFiles],
			[appFolder, files],
		]) {
			for (const [file, source] of Object.entries(sources)) {
				const target = path.join(folder, file)
				fs.mkdirSync(path.dirname(target), { recursive: true })
				fs.writeFileSync(target, source)
			}
		}
		const result = await build({
			configFile: false,
			root: appFolder,
			logLevel: "silent",
			plugins: [
				databaseApp && databaseAppImports(appFolder),
				studioRootAlias(),
				sharedDependencyResolver(frontend),
			],
			build: {
				write: false,
				lib: { entry: path.join(appFolder, "entry.js"), formats: ["es"], fileName: "bundle" },
			},
		})
		return [result]
			.flat()
			.flatMap(({ output }) => output)
			.map((file) => file.code ?? file.source)
			.join("\n")
	} finally {
		fs.rmSync(tmp, { recursive: true, force: true })
	}
}

for (const specifier of ["@app/../../secret.json", "../../../secret.json"]) {
	test(`a database build refuses ${specifier}`, async () => {
		await assert.rejects(
			buildApp({
				"entry.js": 'export { password } from "./stores/leak.js"',
				"stores/leak.js": `import data from "${specifier}"; export const password = data.password`,
			}),
			/resolves outside the app/,
		)
	})
}

test("database CSS keeps @import and url() in the browser", async () => {
	const bundle = await buildApp({
		"entry.js": 'import "./theme.css"',
		"theme.css": '@import "../../secret.css"; .asset { background: url("../../secret.txt") }',
	})
	assert.ok(!bundle.includes(CANARY))
	assert.ok(!bundle.includes(Buffer.from(CANARY).toString("base64")))
})

test("database builds reject import.meta asset reads", async () => {
	await assert.rejects(
		buildApp({
			"entry.js": 'export const asset = new URL("../../secret.txt", import.meta.url).href',
		}),
		/import.meta is not supported/,
	)
})

test("package metadata cannot redirect a database build entry", async () => {
	const bundle = await buildApp({
		"entry.js": "export const value = 42",
		"package.json": JSON.stringify({ browser: { "./entry.js": "../../secret.json" } }),
	})
	assert.ok(!bundle.includes(CANARY))
})

test("repository builds keep TypeScript and Vite asset processing", async () => {
	const bundle = await buildApp(
		{
			"entry.js":
				'import "./theme.css"; export { value } from "./value.ts"; export const asset = new URL("../../secret.txt", import.meta.url).href',
			"value.ts": "export const value: number = 42",
			"theme.css": '@import "../../secret.css";',
		},
		false,
	)
	assert.ok(bundle.includes(CANARY))
})
