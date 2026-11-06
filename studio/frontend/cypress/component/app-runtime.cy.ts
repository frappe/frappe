import { isRef } from "vue"
import { AppModuleRegistry, AppCompileError, clearAppStyles } from "@/browserRuntime/moduleRegistry"

const files: Record<string, string> = {
	"utils/format.ts": `export function fmt(n: number): string { return "#" + n }`,
	"styles/extra.css": ".extra { color: blue }",
	"theme.json": `{"accent": "teal"}`,
	"side-effect.ts": `import "./styles/extra.css"\nimport theme from "./theme.json"\nexport const accent: string = theme.accent`,
	"named-json.ts": `import theme, { accent } from "./theme.json"\nexport const accent2 = accent\nexport const whole = theme`,
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

		cy.wrap(registry.loadModule("named-json.ts")).then((module: any) => {
			// Vite exposes a JSON object's keys as named exports, so the browser must too.
			expect(module.accent2).to.equal("teal")
			expect(module.whole).to.deep.equal({ accent: "teal" })
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

	it("fails only the modules that need a file which does not compile", () => {
		const sources = {
			"good.ts": `export const ok = "ok"`,
			"half-written.ts": `export const oops = (`,
			"needs-broken.ts": `import { oops } from "./half-written"\nexport const x = oops`,
		}

		// a half-written file nothing imports must not stop an unrelated page
		cy.wrap(new AppModuleRegistry(sources).loadModule("good.ts")).then((module: any) => {
			expect(module.ok).to.equal("ok")
		})

		cy.wrap(
			(async () => {
				await expectCompileError(sources, "half-written.ts", "half-written.ts")
				await expectCompileError(sources, "needs-broken.ts", "half-written.ts")
			})(),
		)
	})

	it("checks named imports from the app's own modules", () => {
		cy.wrap(
			(async () => {
				await expectCompileError(
					{
						"utils.ts": `export const one = 1`,
						"a.ts": `import { two } from "./utils"\nexport const x = two`,
					},
					"a.ts",
					'"utils.ts" has no export named "two"',
				)
			})(),
		)

		// A name that does exist must never be reported: through a re-export, from a destructured
		// declaration, and from JSON. A wrong error here would break a working app.
		const sources = {
			"base.ts": `export const one = 1;\nexport const { two, three } = { two: 2, three: 3 };`,
			"barrel.ts": `export * from "./base"\nexport const four = 4`,
			"palette.json": `{"accent": "teal"}`,
			"ok.ts": `import { one, two, three, four } from "./barrel"
import { accent } from "./palette.json"
export const total = one + two + three + four
export const theme = accent`,
		}
		cy.wrap(new AppModuleRegistry(sources).loadModule("ok.ts")).then((module: any) => {
			expect(module.total).to.equal(10)
			expect(module.theme).to.equal("teal")
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
					{ "a.ts": `export const lazy = () => import("./missing-page")` },
					"a.ts",
					"Cannot resolve",
				)
				// A stylesheet import needs its extension, as it does in the app build.
				await expectCompileError(
					{ "a.ts": `import "./theme.css"\nexport const x = 1` },
					"a.ts",
					"Cannot resolve",
				)
			})(),
		)
	})
})
