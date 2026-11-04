import { isRef } from "vue"
import { AppModuleRegistry, AppCompileError, clearAppStyles } from "@/runtime/moduleRegistry"

const files: Record<string, string> = {
	"utils/format.ts": `export function fmt(n: number): string { return "#" + n }`,
	"components/StatCard.vue": `<template><div class="stat">{{ fmt(count) }}<slot /></div></template>
<script setup lang="ts">
import { ref } from "vue"
import { fmt } from "../utils/format"
const count = ref(42)
</script>
<style scoped>.stat { color: rgb(200, 0, 0) }</style>`,
	"components/OptionsCard.vue": `<template><div class="options">{{ label }}</div></template>
<script>
export default { data() { return { label: "from options" } } }
</script>`,
	"styles/extra.css": ".extra { color: blue }",
	"theme.json": `{"accent": "teal"}`,
	"side-effect.ts": `import "./styles/extra.css"\nimport theme from "./theme.json"\nexport const accent: string = theme.accent`,
	"cycle-a.ts": `import { b } from "./cycle-b"\nexport const a = "a"\nexport function readB() { return b }`,
	"cycle-b.ts": `import { a } from "./cycle-a"\nexport const b = "b"\nexport function readA() { return a }`,
}

async function expectCompileError(sources: Record<string, string>, entry: string, needle: string) {
	try {
		await new AppModuleRegistry(sources).loadModule(entry)
		throw new Error(`expected a compile error mentioning: ${needle}`)
	} catch (error: any) {
		expect(error, `error for ${needle}`).to.be.instanceOf(AppCompileError)
		expect(error.message).to.include(needle)
	}
}

describe("AppModuleRegistry", () => {
	afterEach(() => clearAppStyles())

	it("compiles, links and runs an app's modules in the page", () => {
		const registry = new AppModuleRegistry(files)

		cy.wrap(registry.loadModule("components/StatCard.vue")).then((card: any) => {
			expect(card.default.__file).to.equal("components/StatCard.vue")
			expect(card.default.__scopeId).to.match(/^data-v-/)
			cy.mount(card.default).get(".stat").should("contain.text", "#42")
			// Scoped CSS must apply to the mounted component, not just compile successfully.
			cy.get(".stat").should("have.css", "color", "rgb(200, 0, 0)")
		})

		cy.wrap(registry.loadModule("components/OptionsCard.vue")).then((card: any) => {
			// Options API components need a separately compiled template.
			cy.mount(card.default).get(".options").should("contain.text", "from options")
		})

		cy.wrap(registry.loadModule("side-effect.ts")).then((sideEffect: any) => {
			expect(sideEffect.accent).to.equal("teal")
			expect(document.querySelector('style[data-studio-app-css="styles/extra.css"]')).to.exist
		})

		cy.wrap(registry.loadModule("cycle-a.ts")).then((cycleA: any) => {
			expect(cycleA.readB()).to.equal("b")
		})
	})

	it("mounts a page script at its repository path and shares the renderer's vue", () => {
		const registry = new AppModuleRegistry(files)
		const script = `import { ref } from "vue"
import { fmt } from "@app/utils/format"
import { fmt as fmt2 } from "../../utils/format"
export default function setup(context: any) { return { label: ref(fmt(7) + fmt2(8)) } }`

		cy.wrap(
			registry
				.addFile("studio_page/board/board.ts", script)
				.then(() => registry.loadModule("studio_page/board/board.ts")),
		).then((module: any) => {
			const bindings = module.default({})
			expect(bindings.label.value).to.equal("#7#8")
			// The returned binding must retain Vue's ref interface.
			expect(isRef(bindings.label)).to.equal(true)
		})
	})

	it("reads imports from the syntax tree, not from import-like text", () => {
		const sources = {
			"a.ts": `import { ref as count } from "vue"
// import { Gone } from "./deleted.vue"
/** usage: import { Doc } from "./doc-only" */
export const help = 'add import "./theme.css" to the page'
export const sample = \`import { ref } from "vue"\`
export const value = count("ok")`,
		}

		cy.wrap(new AppModuleRegistry(sources).loadModule("a.ts")).then((module: any) => {
			// Validate the exported name "ref" even when the script imports it as "count".
			expect(module.value.value).to.equal("ok")
			expect(module.help).to.include('import "./theme.css"')
		})
	})

	it("reports unresolvable and invalid imports with the file in the message", () => {
		cy.wrap(
			(async () => {
				await expectCompileError({ "a.ts": `import x from "lodash"\nexport const y = x` }, "a.ts", "lodash")
				await expectCompileError(
					{ "a.ts": `import { nope } from "vue"\nexport const y = nope` },
					"a.ts",
					"no export named",
				)
				await expectCompileError(
					{ "a.ts": `import y from "./missing"\nexport const z = y` },
					"a.ts",
					"Cannot resolve",
				)
				// Validate literal dynamic imports before the module executes.
				await expectCompileError(
					{ "a.ts": `export const lazy = () => import("./missing.vue")` },
					"a.ts",
					"Cannot resolve",
				)
				await expectCompileError({ "a.vue": `<template><div :broken="</template>` }, "a.vue", "a.vue")
				// Vue component imports require the .vue extension, as they do in the app build.
				await expectCompileError(
					{
						"a.ts": `import Card from "./Card"\nexport const c = Card`,
						"Card.vue": "<template><b /></template>",
					},
					"a.ts",
					"Cannot resolve",
				)
				// Reject languages that require a preprocessor unavailable in the browser.
				await expectCompileError(
					{ "a.vue": `<template><b /></template>\n<style lang="scss">.x { &:hover { color: red } }</style>` },
					"a.vue",
					'<style lang="scss"> is not supported',
				)
			})(),
		)
	})
})
