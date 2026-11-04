import { pinia } from "../support/component"

import { setActivePinia } from "pinia"
import {
	defineComponent, getCurrentInstance, h, nextTick,
	onMounted, onScopeDispose, onUnmounted, ref, watch,
} from "vue"

import { usePageScope } from "@/stores/codeStore"
import PageScriptHost from "@/components/PageScriptHost.vue"
import type { StudioPage } from "@/types/Studio/StudioPage"

const page = { name: "probe-page", script: "" } as StudioPage

// loadPageScript() seeds the current page with no script; applyPageScriptHotUpdate then installs
// the setup under test, the same path an edited page script takes.
async function installPageScript(setup: unknown) {
	const scope = usePageScope()
	await scope.loadPageScript(page)
	scope.applyPageScriptHotUpdate(page.name, setup)
	return scope
}

const hostMounted = ref(true)

// The host as both environments use it: keyed on the script version, wrapping the page content.
function mountHost(slot?: () => any) {
	hostMounted.value = true
	const scope = usePageScope()
	return cy.mount(
		defineComponent({
			setup: () => () =>
				hostMounted.value
					? h(PageScriptHost, { key: scope.pageScriptVersion }, slot ? { default: slot } : undefined)
					: null,
		}),
	)
}

async function unmountHost() {
	hostMounted.value = false
	await nextTick()
}

const pageBody = () => h("div", { "data-cy": "page" }, "page body")

describe("page script host", () => {
	beforeEach(() => setActivePinia(pinia))
	afterEach(() => {
		hostMounted.value = false
		usePageScope().teardownPage()
	})

	it("runs setup in a component instance, so onMounted fires", () => {
		let hadInstance = false
		let mountedRan = false
		cy.wrap(
			installPageScript(() => {
				hadInstance = Boolean(getCurrentInstance())
				onMounted(() => (mountedRan = true))
				return {}
			}),
		)
		mountHost()

		cy.then(() => {
			expect(hadInstance, "setup saw a component instance").to.be.true
			expect(mountedRan, "onMounted ran").to.be.true
		})
	})

	it("fires onUnmounted when the host unmounts", () => {
		let unmountedRan = false
		cy.wrap(installPageScript(() => (onUnmounted(() => (unmountedRan = true)), {})))
		mountHost()

		cy.then(() => expect(unmountedRan, "onUnmounted ran while still mounted").to.be.false)
		cy.wrap(null).then(unmountHost)
		cy.then(() => expect(unmountedRan, "onUnmounted ran").to.be.true)
	})

	// repository apps in the wild (helpdesk's portal) unregister socket handlers this way
	it("still runs onScopeDispose, which the instance's own scope owns", () => {
		let disposed = false
		cy.wrap(installPageScript(() => (onScopeDispose(() => (disposed = true)), {})))
		mountHost()

		cy.then(() => expect(disposed, "disposed while still mounted").to.be.false)
		cy.wrap(null).then(unmountHost)
		cy.then(() => expect(disposed, "onScopeDispose ran").to.be.true)
	})

	it("disposes a watcher the script created when the host unmounts", () => {
		const source = ref(0)
		let fired = 0
		cy.wrap(installPageScript(() => (watch(source, () => fired++), {})))
		mountHost()

		cy.wrap(null).then(async () => {
			source.value = 1
			await nextTick()
		})
		cy.then(() => expect(fired, "watcher did not fire while mounted").to.equal(1))

		cy.wrap(null).then(unmountHost)
		cy.wrap(null).then(async () => {
			source.value = 2
			await nextTick()
		})
		cy.then(() => expect(fired, "watcher outlived the page").to.equal(1))
	})

	it("stops the script when the page is torn down", () => {
		const source = ref(0)
		let fired = 0
		cy.wrap(installPageScript(() => (watch(source, () => fired++), {})))
		mountHost()

		cy.wrap(null).then(async () => {
			usePageScope().teardownPage()
			await nextTick()
			source.value = 1
			await nextTick()
		})
		cy.then(() => expect(fired, "watcher outlived the page").to.equal(0))
	})

	it("runs a changed script in a new instance and tears the old one down", () => {
		const ran: string[] = []
		cy.wrap(installPageScript(() => (ran.push("first"), onUnmounted(() => ran.push("first torn down")), {})))
		mountHost()

		cy.wrap(null).then(async () => {
			usePageScope().applyPageScriptHotUpdate(page.name, () => (ran.push("second"), {}))
			await nextTick()
		})
		cy.then(() => {
			expect(ran, "the new script ran").to.include("second")
			expect(ran, "the old instance was torn down").to.include("first torn down")
		})
	})

	it("renders the page once, with a synchronous setup's bindings already in place", () => {
		const scope = usePageScope()
		const renders: string[] = []
		cy.wrap(installPageScript(() => ({ title: "now" })))
		mountHost(() => {
			renders.push(String(scope.pageScriptBindings.title))
			return h("div", { "data-cy": "page" }, String(scope.pageScriptBindings.title))
		})

		cy.get("[data-cy=page]").should("have.text", "now")
		cy.then(() => expect(renders, "the page rendered before its bindings").to.deep.equal(["now"]))
	})

	it("holds the page back until an async setup resolves", () => {
		let finishSetup: (bindings: any) => void = () => {}
		cy.wrap(installPageScript(() => new Promise((resolve) => (finishSetup = resolve))))
		mountHost(pageBody)

		cy.get("[data-cy=page]").should("not.exist")
		cy.then(() => {
			expect(usePageScope().pageScriptReady, "ready before the setup resolved").to.be.false
			finishSetup({ title: "ready" })
		})
		cy.get("[data-cy=page]").should("exist")
		cy.then(() => expect(usePageScope().pageScriptBindings.title).to.equal("ready"))
	})

	it("ignores bindings from a script that was replaced while it was still running", () => {
		let finishFirst: (bindings: any) => void = () => {}
		cy.wrap(installPageScript(() => new Promise((resolve) => (finishFirst = resolve))))
		mountHost()

		cy.wrap(null).then(async () => {
			usePageScope().applyPageScriptHotUpdate(page.name, () => ({ from: "second" }))
			await nextTick()
			finishFirst({ from: "first" })
			await nextTick()
		})
		cy.then(() => expect(usePageScope().pageScriptBindings.from).to.equal("second"))
	})

	it("reports a setup that throws and still renders the page", () => {
		cy.wrap(
			installPageScript(() => {
				throw new Error("boom")
			}),
		)
		mountHost(pageBody)

		cy.get("[data-cy=page]").should("exist")
		cy.then(() => expect(usePageScope().pageScriptError).to.include("boom"))
	})
})
