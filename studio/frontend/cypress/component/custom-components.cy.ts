import {
	componentHasDefaultSlot,
	getComponentSlots,
	getComponentTemplate,
	registerCustomComponentPaths,
} from "@/utils/componentSlots"

const cardIn = (app: string) => ({
	component_name: "Card",
	studio_app: app,
	file_path: new URL(`../fixtures/custom-components/${app}/Card.vue`, import.meta.url).pathname,
	studio_file_path: "Card.vue",
})

describe("custom components", () => {
	beforeEach(() => registerCustomComponentPaths([]))

	it("re-reads the slots of a component whose file changed with the app", async () => {
		await registerCustomComponentPaths([cardIn("app_a")])
		expect(await getComponentSlots("Card", true)).to.deep.equal([{ name: "header", type: "named" }])

		await registerCustomComponentPaths([cardIn("app_b")])
		expect(await getComponentSlots("Card", true)).to.deep.equal([
			{ name: "default", type: "default" },
			{ name: "footer", type: "named" },
		])
		expect(componentHasDefaultSlot("Card")).to.equal(true)

		await registerCustomComponentPaths([])
		expect(await getComponentSlots("Card", true)).to.deep.equal([])
		expect(componentHasDefaultSlot("Card")).to.equal(false)

		await registerCustomComponentPaths([cardIn("app_a")])
		expect(await getComponentSlots("Card", true)).to.deep.equal([{ name: "header", type: "named" }])
	})

	it("ignores an earlier app's component import after switching apps", () => {
		cy.stub(Date, "now").returns(0)
		cy.then(async () => {
			// Warm B's module so it resolves before A's first import of its distinct URL.
			await registerCustomComponentPaths([cardIn("app_b")])
			const earlierLoad = registerCustomComponentPaths([cardIn("app_a")])
			await registerCustomComponentPaths([cardIn("app_b")])
			await earlierLoad

			expect(await getComponentSlots("Card", true)).to.deep.equal([
				{ name: "default", type: "default" },
				{ name: "footer", type: "named" },
			])
			expect(componentHasDefaultSlot("Card")).to.equal(true)
			expect(getComponentTemplate("Card")).to.contain('name="footer"')
		})
	})
})
