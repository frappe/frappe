import { AppModuleRegistry, clearAppStyles } from "@/browserRuntime/moduleRegistry"
import { loadImportableModule } from "@/browserRuntime/importableModules"
import { IMPORTABLE_MODULES } from "@/browserRuntime/importableLibraries.js"
import { moduleFixtures } from "../fixtures/module-fixtures.mjs"
import { STUDIO_SHARED_DEPS } from "../../vite/sharedDependencyResolver"

async function outcome(load: () => Promise<any>) {
	try {
		const module = await load()
		return { value: await module.run() }
	} catch (error: any) {
		return { error: error.message || String(error) }
	}
}

function resetProbe() {
	;(globalThis as any).__moduleFixtureOrder = []
}

async function loadStyles(base: string, files: string[]) {
	for (const file of files) {
		await new Promise<void>((resolve, reject) => {
			const link = document.createElement("link")
			link.rel = "stylesheet"
			link.dataset.moduleFixture = "true"
			link.href = base + file
			link.onload = () => resolve()
			link.onerror = () => reject(new Error(`Cannot load ${link.href}`))
			document.head.append(link)
		})
	}
}

describe("DB app modules: browser registry and Vite build", () => {
	afterEach(() => {
		clearAppStyles()
		document.querySelectorAll("link[data-module-fixture]").forEach((link) => link.remove())
		delete (globalThis as any).__moduleFixtureOrder
	})

	for (const fixture of moduleFixtures) {
		it(fixture.name, () => {
			cy.wrap(
				(async () => {
					resetProbe()
					const registry = new AppModuleRegistry(fixture.files)
					const preview = await outcome(() => registry.loadModule("entry.js"))
					clearAppStyles()
					resetProbe()
					const base = new URL(`/__studio_parity__/${fixture.name}/`, window.location.origin).href
					const response = await fetch(base + "report.json")
					expect(response.ok, "fixture build endpoint").to.equal(true)
					const report = await response.json()
					if (report.ok) await loadStyles(base, report.css)
					const built = report.ok
						? await outcome(() => import(/* @vite-ignore */ base + "entry.js"))
						: { error: report.error }
					if (fixture.failureContains) {
						expect(preview.error, "preview must reject").to.include(fixture.failureContains)
						expect(report.ok, "build accepts it").to.equal(Boolean(fixture.previewOnly))
					} else {
						expect(preview.error, "preview error").to.equal(undefined)
						expect(built.error, "build error").to.equal(undefined)
						expect(preview.value, "preview result").to.deep.equal(fixture.expected)
						expect(built.value, "built result").to.deep.equal(fixture.expected)
					}
				})(),
				{ timeout: 60000 },
			)
		})
	}

	it("only offers libraries a real build can resolve", () => {
		// A database app's temporary build folder has no node_modules directory, so every offered
		// library must resolve to Studio's installed dependencies.
		const unresolvable = IMPORTABLE_MODULES.filter(
			(specifier) => !STUDIO_SHARED_DEPS.some((dep) => specifier === dep || specifier.startsWith(`${dep}/`)),
		)
		expect(unresolvable, "importable but unresolvable in a build").to.deep.equal([])

		cy.wrap(Promise.all(IMPORTABLE_MODULES.map(loadImportableModule))).then((modules) => {
			for (const module of modules) expect(Object.keys(module)).not.to.be.empty
		})
	})

	it("keeps a failed module failed without executing it a second time", () => {
		cy.wrap(
			(async () => {
				const registry = new AppModuleRegistry({
					"entry.js": `globalThis.__failedModuleRuns++; throw new Error('fixture failed')`,
				})
				;(globalThis as any).__failedModuleRuns = 0
				for (let attempt = 0; attempt < 2; attempt++) {
					const result = await outcome(() => registry.loadModule("entry.js"))
					expect(result.error).to.include("fixture failed")
				}
				expect((globalThis as any).__failedModuleRuns).to.equal(1)
				delete (globalThis as any).__failedModuleRuns
			})(),
		)
	})
})
