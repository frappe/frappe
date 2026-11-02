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
		}).then(({ wrapper }) => {
			const element = wrapper.element as HTMLElement
			expect(element.querySelector("script")).to.be.null
			expect(element.querySelector("img")?.hasAttribute("onerror")).to.be.false
			expect(element.querySelector("svg")?.hasAttribute("onload")).to.be.false
			expect(element.querySelector("a")?.hasAttribute("href")).to.be.false
		})

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
