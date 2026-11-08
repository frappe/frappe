import { isRef } from "vue"
import { AppModuleRegistry, AppCompileError, clearAppStyles } from "@/browserRuntime/moduleRegistry"

// Linking, execution order and export resolution are checked against a real build in
// module-parity.cy.ts. This spec covers only what the registry itself does.

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

	it("fails only the modules a broken file breaks, and keeps them failed", () => {
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

				// A module that stops compiling must not keep running the last version that did,
				// or a broken script looks fine again after a reload.
				const registry = new AppModuleRegistry({ "a.js": `export const value = 1` })
				expect((await registry.loadModule("a.js")).value).to.equal(1)
				for (const attempt of ["first", "second"]) {
					let saveError: any = null
					await registry.addFile("a.js", `export const value = (`).catch((e) => (saveError = e))
					expect(saveError, `${attempt} save rejected`).to.be.instanceOf(AppCompileError)
				}
				let loadError: any = null
				await registry.loadModule("a.js").catch((e) => (loadError = e))
				expect(loadError, "loading it reports the failure").to.be.instanceOf(AppCompileError)

				// A missing export is the one failure that leaves a working factory behind, so an
				// unchanged script has to keep reporting it instead of running an undefined import.
				const pageRegistry = new AppModuleRegistry({ "utils.js": `export const present = 1` })
				const page = "studio_page/board/board.js"
				const missingExport = `import { missing } from "@app/utils.js"\nexport default () => missing`
				for (const attempt of ["first", "second"]) {
					let importError: any = null
					await pageRegistry.addFile(page, missingExport).catch((e) => (importError = e))
					expect(importError, `${attempt} save rejected`).to.be.instanceOf(AppCompileError)
					expect(importError.message).to.include(`has no export named "missing"`)
				}
				const fixed = `import { present } from "@app/utils.js"\nexport default () => present`
				await pageRegistry.addFile(page, fixed)
				expect((await pageRegistry.loadModule(page)).default()).to.equal(1)
			})(),
		)
	})

	it("runs the source as it is, so typescript syntax is a syntax error", () => {
		cy.wrap(expectCompileError({ "a.js": `export const n: number = 1` }, "a.js", "a.js"))
	})

	it("reports unresolvable and invalid imports with the file in the message", () => {
		cy.wrap(
			(async () => {
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
