import assert from "node:assert/strict"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"
import { build } from "vite"
import databaseAppImports from "./databaseAppImports.js"
import sharedDependencyResolver from "./sharedDependencyResolver.js"
import studioRootAlias from "./studioRootAlias.js"

// A database app's build folder has no node_modules, so libraries resolve to Studio's own.
const frontend = fileURLToPath(new URL("../", import.meta.url))

/** Build one app folder the way a published database app is built, and return the bundle or the error. */
async function buildApp(files, outsideFiles = {}) {
	const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "studio-db-imports-"))
	const appFolder = path.join(tmp, "studio", "shop")
	for (const [target, source] of [
		...Object.entries(outsideFiles).map(([file, body]) => [path.join(tmp, file), body]),
		...Object.entries(files).map(([file, body]) => [path.join(appFolder, file), body]),
	]) {
		fs.mkdirSync(path.dirname(target), { recursive: true })
		fs.writeFileSync(target, source)
	}
	const outDir = path.join(tmp, "out")
	try {
		await build({
			configFile: false,
			root: appFolder,
			logLevel: "silent",
			plugins: [databaseAppImports(appFolder), studioRootAlias(), sharedDependencyResolver(frontend)],
			build: {
				outDir,
				emptyOutDir: true,
				lib: { entry: path.join(appFolder, "entry.js"), formats: ["es"], fileName: "bundle" },
			},
		})
		const bundle = fs
			.readdirSync(outDir)
			.map((file) => fs.readFileSync(path.join(outDir, file), "utf8"))
			.join("\n")
		return { ok: true, bundle }
	} catch (error) {
		return { ok: false, error: String(error.message) }
	} finally {
		fs.rmSync(tmp, { recursive: true, force: true })
	}
}

const SECRET = { "secrets.json": '{"password":"CANARY"}' }

test("a database app's build refuses an import that leaves the app folder", async () => {
	// `@app/` is only a prefix: path.join normalises `..`, so it can walk out of the app.
	const viaPrefix = await buildApp(
		{
			"entry.js": `export { password } from "./stores/leak.js"`,
			"stores/leak.js": `import data from "@app/../../secrets.json"\nexport const password = data.password`,
		},
		SECRET,
	)
	assert.equal(viaPrefix.ok, false)
	assert.match(viaPrefix.error, /must not walk above the app root/)

	const viaRelative = await buildApp(
		{
			"entry.js": `export { password } from "./stores/leak.js"`,
			"stores/leak.js": `import data from "../../../secrets.json"\nexport const password = data.password`,
		},
		SECRET,
	)
	assert.equal(viaRelative.ok, false)
	assert.match(viaRelative.error, /resolves outside the app/)

	// A query suffix must not hide the path: ?raw would otherwise inline any file as a string.
	const viaRaw = await buildApp(
		{
			"entry.js": `export { text } from "./stores/leak.js"`,
			"stores/leak.js": `import text from "../../../secrets.json?raw"\nexport { text }`,
		},
		SECRET,
	)
	assert.equal(viaRaw.ok, false)
	assert.match(viaRaw.error, /resolves outside the app/)

	const viaLibrary = await buildApp({
		"entry.js": `import value from "lodash"\nexport const total = value`,
	})
	assert.equal(viaLibrary.ok, false)
	assert.match(viaLibrary.error, /is not importable in a database app/)
})

test("a database app's build keeps resolving its own files and allowed libraries", async () => {
	const built = await buildApp(
		{
			"entry.js": `export { label } from "./studio_page/board/board.js"`,
			"utils/format.js": `export const fmt = (n) => "#" + n`,
			"theme.json": `{"accent":"teal"}`,
			"studio_page/board/board.js": `import { isRef, ref } from "vue"
import { fmt } from "@app/utils/format"
import { fmt as fmt2 } from "../../utils/format"
import theme from "@app/theme.json"
export const label = fmt(1) + fmt2(2) + theme.accent + isRef(ref(0))`,
		},
		SECRET,
	)
	assert.equal(built.ok, true, built.error)
	assert.ok(!built.bundle.includes("CANARY"))
})
