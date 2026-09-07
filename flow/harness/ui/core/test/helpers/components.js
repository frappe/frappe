import { readFile } from "node:fs/promises"

import { compileScript, parse } from "vue/compiler-sfc"

const vue = import.meta.resolve("vue")
const moduleURL = (code) => `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
const stub = moduleURL(`
	import { h } from ${JSON.stringify(vue)}
	export default { render() { return h('div', this.$slots.default?.()) } }
`)
const dialogs = moduleURL(`import { ref } from ${JSON.stringify(vue)}; export const dialogs = ref([])`)
const components = new Set(["Composer.vue", "ToolStep.vue", "ToolGroup.vue", "ApprovalCard.vue"])
const compiled = new Map()

// Compile the real templates for DOM tests; unrelated child widgets are shallow
// stubs. File URLs keep normal JS imports on Node's shared module/Vue instance.
async function componentURL(url) {
	if (compiled.has(url.href)) return compiled.get(url.href)
	const source = await readFile(url, "utf8")
	const { descriptor } = parse(source, { filename: url.pathname })
	let { content } = compileScript(descriptor, { id: url.pathname, inlineTemplate: true })
	const imports = [...content.matchAll(/\bfrom\s+["']([^"']+)["']/g)]
	for (const match of imports.reverse()) {
		const specifier = match[1]
		let resolved
		if (specifier.endsWith(".vue")) {
			resolved = components.has(specifier.split("/").pop())
				? await componentURL(new URL(specifier, url))
				: stub
		} else if (specifier === "frappe-ui/src/utils/dialog") {
			resolved = dialogs
		} else {
			resolved = specifier.startsWith(".") ? new URL(specifier, url).href : import.meta.resolve(specifier)
		}
		content = content.slice(0, match.index) + `from ${JSON.stringify(resolved)}` + content.slice(match.index + match[0].length)
	}
	const result = moduleURL(content)
	compiled.set(url.href, result)
	return result
}

export async function loadComponent(name) {
	const url = new URL(`../../src/components/${name}.vue`, import.meta.url)
	return (await import(await componentURL(url))).default
}
