import assert from "node:assert/strict"
import test from "node:test"
import { fileURLToPath } from "node:url"
import { build } from "vite"

const pageLoader = fileURLToPath(new URL("../../src/page/pageLoader.ts", import.meta.url))

async function loadRuntime() {
	const modules = {
		"test-state": `
			export let currentRouter
			export const pending = new Map()
			export function selectRouter(router) { currentRouter = router }
			export function runWithRouter(router, run) {
				const previous = currentRouter
				currentRouter = router
				try { return run() } finally { currentRouter = previous }
			}
		`,
		vue: `
			import { currentRouter } from "test-state"
			export const shallowRef = value => ({ value })
			export const watch = () => {}
			export const inject = key => currentRouter.provides[key]
		`,
		"vue-router": `export { currentRouter as useRouterValue } from "test-state"
			import { currentRouter } from "test-state"
			export const useRouter = () => currentRouter`,
		"@/utils/helpers": `
			import { pending } from "test-state"
			export const fetchAppPage = (app, page) => new Promise(resolve => pending.set(app, resolve))
		`,
		"@/utils/serializer": `export const getBlockInstance = block => block`,
		"@/stores/componentStore": `
			import { currentRouter } from "test-state"
			export default () => currentRouter.componentStore
		`,
		"@/page/pageScope": `export function createPageScope(route, router, components, socket) {
			return {
				components, socket, tornDown: false,
				setPageVariables: async () => {}, setPageResources: async () => {}, loadPageScript: async () => {},
				teardownPage() { this.tornDown = true },
			}
		}`,
	}
	const result = await build({
		configFile: false,
		logLevel: "silent",
		plugins: [
			{
				name: "page-loader-test",
				enforce: "pre",
				resolveId: (id) => (id in modules || id === "test-entry" ? `\0${id}` : undefined),
				load: (id) =>
					id === "\0test-entry"
						? `export * from ${JSON.stringify(pageLoader)}; export * from "test-state"`
						: modules[id.slice(1)],
			},
		],
		build: {
			write: false,
			minify: false,
			rolldownOptions: { input: "test-entry", preserveEntrySignatures: "strict" },
		},
	})
	return import(`data:text/javascript;base64,${Buffer.from(result.output[0].code).toString("base64")}`)
}

function makeRouter(name, runtime) {
	const router = {
		provides: { appComponents: { Button: { name } }, socket: { name } },
		currentRoute: { value: { fullPath: "/board" } },
		componentStore: {
			app: null,
			setStudioApp(app) {
				this.app = app
			},
			setComponents: async () => {},
		},
	}
	router.provides.vueApp = { runWithContext: (run) => runtime.runWithRouter(router, run) }
	return router
}

function route(app) {
	return { fullPath: "/board", meta: { appName: app, pageName: `${app}-board` } }
}

function page(app) {
	return { name: `${app}-board`, blocks: "[{}]", components: [] }
}

test("concurrent routers retain their own loaded pages and app context", async () => {
	globalThis.window = {}
	const runtime = await loadRuntime()
	const a = makeRouter("a", runtime)
	const b = makeRouter("b", runtime)
	runtime.selectRouter(a)
	const first = runtime.loadPage(a, route("a"), { meta: {} })
	runtime.selectRouter(b)
	const second = runtime.loadPage(b, route("b"), { meta: {} })
	runtime.pending.get("b")(page("b"))
	await second
	runtime.pending.get("a")(page("a"))
	await first

	runtime.selectRouter(a)
	const loadedA = runtime.useLoadedPage()
	assert.equal(loadedA.page.name, "a-board")
	assert.equal(loadedA.scope.components, a.provides.appComponents)
	assert.equal(a.componentStore.app, "a")
	runtime.discardPage(a, route("a"), new Error("cancelled"))
	runtime.selectRouter(b)
	const loadedB = runtime.useLoadedPage()
	assert.equal(loadedB.page.name, "b-board")
	assert.equal(loadedB.scope.components, b.provides.appComponents)
	assert.equal(loadedB.scope.tornDown, false)
	assert.equal(b.componentStore.app, "b")
	delete globalThis.window
})
