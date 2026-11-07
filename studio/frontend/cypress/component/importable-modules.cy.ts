import { IMPORTABLE_MODULES } from "@/browserRuntime/importableModules"
import { STUDIO_SHARED_DEPS } from "../../vite/sharedDependencyResolver"

describe("the database app import map", () => {
	it("only offers modules a real Vite build can resolve", () => {
		// The temporary database-app build has no node_modules directory.
		// Every offered library must resolve to Studio's installed dependencies.
		const unresolvable = IMPORTABLE_MODULES.filter(
			(specifier) => !STUDIO_SHARED_DEPS.some((dep) => specifier === dep || specifier.startsWith(`${dep}/`)),
		)
		expect(unresolvable, "importable but unresolvable in a build").to.deep.equal([])
	})
})
