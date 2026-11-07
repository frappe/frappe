import { isRef } from "vue"
import { AppModuleRegistry, AppCompileError, clearAppStyles } from "@/browserRuntime/moduleRegistry"

// Linking, execution order and export resolution are checked against a real build in
// module-parity.cy.ts. This spec covers what only the registry does: adding a file to a loaded
// app, keeping one broken file local, and the rules that exist because the browser runs the
// source as it is.

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

	it("mounts a page script at its repository path and shares the renderer's vue", () => {
		const registry = new AppModuleRegistry({ "utils/format.js": `export function fmt(n) { return "#" + n }` })
		const script = `import { ref } from "vue"
import { fmt } from "@app/utils/format"
import { fmt as fmt2 } from "../../utils/format"
export default function setup(context) { return { label: ref(fmt(7) + fmt2(8)) } }`

		cy.wrap(
			registry
				.addFile("studio_page/board/board.js", script)
				.then(() => registry.loadModule("studio_page/board/board.js")),
		).then((module: any) => {
			const bindings = module.default({})
			expect(bindings.label.value).to.equal("#7#8")
			// The returned binding must retain Vue's ref interface.
			expect(isRef(bindings.label)).to.equal(true)
		})
	})

	it("fails only the modules that need a file which does not compile", () => {
		const sources = {
			"good.js": `export const ok = "ok"`,
			"half-written.js": `export const oops = (`,
			"needs-broken.js": `import { oops } from "./half-written"\nexport const x = oops`,
		}

		// a half-written file nothing imports must not stop an unrelated page
		cy.wrap(new AppModuleRegistry(sources).loadModule("good.js")).then((module: any) => {
			expect(module.ok).to.equal("ok")
		})

		cy.wrap(
			(async () => {
				await expectCompileError(sources, "half-written.js", "half-written.js")
				await expectCompileError(sources, "needs-broken.js", "half-written.js")
			})(),
		)
	})

	it("reports a missing named import, and never reports one the target does declare", () => {
		cy.wrap(
			(async () => {
				await expectCompileError(
					{
						"utils.js": `export const one = 1`,
						"a.js": `import { two } from "./utils"\nexport const x = two`,
					},
					"a.js",
					'"utils.js" has no export named "two"',
				)
			})(),
		)

		// A destructured export declares every name in its pattern. A wrong error here would
		// break a working app.
		const sources = {
			"base.js": `export const { two, three } = { two: 2, three: 3 }`,
			"ok.js": `import { two, three } from "./base"\nexport const total = two + three`,
		}
		cy.wrap(new AppModuleRegistry(sources).loadModule("ok.js")).then((module: any) => {
			expect(module.total).to.equal(5)
		})
	})

	it("runs the source as it is, so typescript syntax is a syntax error", () => {
		cy.wrap(expectCompileError({ "a.js": `export const n: number = 1` }, "a.js", "a.js"))
	})

	it("reports unresolvable and invalid imports with the file in the message", () => {
		cy.wrap(
			(async () => {
				await expectCompileError({ "a.js": `import x from "lodash"\nexport const y = x` }, "a.js", "lodash")
				await expectCompileError(
					{ "a.js": `import y from "./missing"\nexport const z = y` },
					"a.js",
					"Cannot resolve",
				)
				// Validate literal dynamic imports before the module executes.
				await expectCompileError(
					{ "a.js": `export const lazy = () => import("./missing-page")` },
					"a.js",
					"Cannot resolve",
				)
				// A stylesheet import needs its extension, as it does in the app build.
				await expectCompileError(
					{ "a.js": `import "./theme.css"\nexport const x = 1` },
					"a.js",
					"Cannot resolve",
				)
			})(),
		)
	})
})
