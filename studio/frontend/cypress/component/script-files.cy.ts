import { toast } from "frappe-ui"
import { resolveScriptPath } from "@/data/studioFiles"
import { checkAppScript } from "@/browserRuntime/appRuntime"
import RouterScript from "@/components/RouterScript.vue"
import useStudioStore from "@/stores/studioStore"
import type { StudioApp } from "@/types/Studio/StudioApp"

describe("Studio script files", () => {
	beforeEach(() => {
		const store = useStudioStore()
		store.studioLayout.showLeftPanel = true
		store.studioLayout.leftPanelActiveTab = "Pages"
		cy.document().then((doc) => {
			const outlet = doc.createElement("div")
			outlet.id = "studio-code-editor-outlet"
			doc.body.append(outlet)
		})
	})

	afterEach(() => {
		useStudioStore().showRouterEditor = false
		cy.document().then((doc) => doc.getElementById("studio-code-editor-outlet")?.remove())
	})

	it("defaults repository scripts to TypeScript and DB scripts to JavaScript", () => {
		for (const stem of ["router", "studio_page/board/board"]) {
			expect(resolveScriptPath(stem, [], false)).to.equal(`${stem}.ts`)
			expect(resolveScriptPath(stem, [], true)).to.equal(`${stem}.js`)
		}
	})

	it("preserves either existing repository extension and rejects duplicate companions", () => {
		for (const stem of ["router", "studio_page/board/board"]) {
			for (const extension of ["js", "ts"]) {
				const path = `${stem}.${extension}`
				expect(resolveScriptPath(stem, [path], false)).to.equal(path)
			}
			expect(() => resolveScriptPath(stem, [`${stem}.ts`, `${stem}.js`], false)).to.throw("Keep only one")
		}
	})

	it("checks TypeScript syntax in repository scripts without accepting it in JavaScript", () => {
		cy.wrap(
			(async () => {
				const source = `import type { Ref } from "vue"; export default function setup(context: { count: Ref<number> }) { return { count: context.count } }`
				expect(await checkAppScript(source, "board.ts")).to.equal(null)
				expect(await checkAppScript(source, "board.js")).to.be.a("string")
				expect(await checkAppScript("export const value = (", "board.ts")).to.be.a("string")
			})(),
		)
	})

	for (const [isStandard, extension] of [
		[1, "ts"],
		[0, "js"],
	] as const) {
		it(`creates ${isStandard ? "repository" : "DB"} router.${extension}`, () => {
			cy.intercept("POST", "**/api/method/frappe.studio.api.read_studio_file", (req) => {
				req.reply({ message: { path: req.body.file_path, content: null, hash: null } })
			})
			cy.intercept("POST", "**/api/method/frappe.studio.api.write_studio_file", (req) => {
				expect(req.body.file_path).to.equal(`router.${extension}`)
				req.reply({ message: { path: req.body.file_path, hash: "saved" } })
			}).as("writeRouter")
			const store = useStudioStore()
			store.activeApp = {
				name: "script-files",
				is_standard: isStandard,
				frappe_app: isStandard ? "frappe" : "",
			} as StudioApp
			store.activePage = null
			store.showRouterEditor = true
			cy.mount(RouterScript)
			cy.contains(`router.${extension}`).should("be.visible")
			cy.contains("button", "Save").click()
			cy.wait("@writeRouter")
		})
	}

	it("opens an existing JavaScript repository router without changing its extension", () => {
		cy.intercept("POST", "**/api/method/frappe.studio.api.read_studio_file", (req) => {
			const content = req.body.file_path === "router.js" ? "export default {}" : null
			req.reply({ message: { path: req.body.file_path, content, hash: content ? "existing" : null } })
		})
		const store = useStudioStore()
		store.activeApp = { name: "script-files", is_standard: 1, frappe_app: "frappe" } as StudioApp
		store.showRouterEditor = true
		cy.mount(RouterScript)
		cy.contains("router.js").should("be.visible")
	})

	it("reports duplicate router companions instead of choosing one", () => {
		cy.intercept("POST", "**/api/method/frappe.studio.api.read_studio_file", (req) => {
			req.reply({ message: { path: req.body.file_path, content: "export default {}", hash: "existing" } })
		})
		cy.stub(toast, "error").as("error")
		const store = useStudioStore()
		store.activeApp = { name: "script-files", is_standard: 1, frappe_app: "frappe" } as StudioApp
		store.showRouterEditor = true
		cy.mount(RouterScript)
		cy.get("@error").should("have.been.calledWithMatch", "Failed to open the router script", {
			description: Cypress.sinon.match("Keep only one"),
		})
	})
})
