import HTMLBlock from "@/components/AppLayout/HTML.vue"
import { sanitizeHTML } from "@/utils/helpers"

describe("sanitizeHTML", () => {
	it("removes executable markup before rendering an HTML block", () => {
		;(window as any).studioXss = false

		cy.mount(HTMLBlock, {
			props: {
				html: `
			<script>window.studioXss = true</script>
			<img src="x" onerror="window.studioXss = true">
			<svg onload="window.studioXss = true"></svg>
			<a href="javascript:window.studioXss = true">Click</a>
		`,
			},
		})

		cy.get("script").should("not.exist")
		cy.get("img").should("not.have.attr", "onerror")
		cy.get("svg").should("not.have.attr", "onload")
		cy.get("a").should("not.have.attr", "href")
		cy.then(() => expect((window as any).studioXss).to.be.false)
	})

	it("preserves safe HTML and CSS custom properties", () => {
		const sanitized = sanitizeHTML(
			'<section class="card" style="color: var(--text-color)"><strong>Hello</strong></section>',
		)

		expect(sanitized).to.contain('<section class="card"')
		expect(sanitized).to.contain("var(--text-color)")
		expect(sanitized).to.contain("<strong>Hello</strong>")
	})
})
