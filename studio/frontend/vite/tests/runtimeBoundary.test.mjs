import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import test from "node:test"
import { fileURLToPath } from "node:url"
import ts from "typescript"
import { parse } from "vue/compiler-sfc"

const src = fileURLToPath(new URL("../../src/", import.meta.url))
const runtime = path.join(src, "runtime")
const allowed = [runtime, path.join(src, "types")]

// The renderer and the desk island are built from src/runtime. An import from the rest of src
// would ship editor code to every user of a Studio app.
test("runtime code imports nothing from src outside src/runtime and src/types", () => {
	const imports = fs
		.readdirSync(runtime, { recursive: true })
		.filter((file) => /\.(ts|js|mjs|vue)$/.test(file) && !file.endsWith(".d.ts"))
		.flatMap((file) => getImports(path.join(runtime, file)))
	assert.ok(imports.length, "found no imports in src/runtime")

	const outside = imports.filter(
		({ target }) => isInside(src, target) && !allowed.some((dir) => isInside(dir, target)),
	)
	assert.deepEqual(
		outside.map(({ file, specifier }) => `${path.relative(src, file)} imports ${specifier}`),
		[],
	)
})

function getImports(file) {
	return ts
		.preProcessFile(getScript(file), true, true)
		.importedFiles.map(({ fileName: specifier }) => ({ file, specifier, target: resolve(specifier, file) }))
		.filter(({ target }) => target)
}

function getScript(file) {
	const source = fs.readFileSync(file, "utf8")
	if (!file.endsWith(".vue")) return source
	const { script, scriptSetup } = parse(source).descriptor
	return [script?.content, scriptSetup?.content].filter(Boolean).join("\n")
}

function resolve(specifier, file) {
	if (specifier.startsWith("@/")) return path.join(src, specifier.slice(2))
	if (specifier.startsWith(".")) return path.resolve(path.dirname(file), specifier)
	return null
}

function isInside(dir, target) {
	return !path.relative(dir, target).startsWith("..")
}
