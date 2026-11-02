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
			// the scoped style landed in the document and applies to the mounted component
			cy.get(".stat").should("have.css", "color", "rgb(200, 0, 0)")
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
			// isRef only recognizes refs made by the same vue instance the editor runs on
			expect(isRef(bindings.label)).to.equal(true)
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
				await expectCompileError({ "a.vue": `<template><div :broken="</template>` }, "a.vue", "a.vue")
				// .vue files resolve only with an explicit extension, like the real Vite build
				await expectCompileError(
					{
						"a.ts": `import Card from "./Card"\nexport const c = Card`,
						"Card.vue": "<template><b /></template>",
					},
					"a.ts",
					"Cannot resolve",
				)
				// a preprocessor the browser does not have must fail, not compile to wrong output
				await expectCompileError(
					{ "a.vue": `<template><b /></template>\n<style lang="scss">.x { &:hover { color: red } }</style>` },
					"a.vue",
					'<style lang="scss"> is not supported',
				)
			})(),
		)
	})
})
