import { IMPORTABLE_MODULES } from "@/runtime/importableModules"
import { STUDIO_SHARED_DEPS } from "../../vite/sharedDependencyResolver"

describe("the database app import map", () => {
	it("only offers modules a real Vite build can resolve", () => {
		// A database app's sources build from a staged temp folder with no node_modules of its own,
		// so every importable specifier must be redirected to Studio's copy by the build resolver.
		const unresolvable = IMPORTABLE_MODULES.filter(
			(specifier) => !STUDIO_SHARED_DEPS.some((dep) => specifier === dep || specifier.startsWith(`${dep}/`)),
		)
		expect(unresolvable, "importable but unresolvable in a build").to.deep.equal([])
	})
})
