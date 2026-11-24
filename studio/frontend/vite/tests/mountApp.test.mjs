import assert from "node:assert/strict"
import { existsSync } from "node:fs"
import { createRequire } from "node:module"
import test from "node:test"
import { fileURLToPath, pathToFileURL } from "node:url"
import { build } from "vite"

const source = fileURLToPath(new URL("../../src/", import.meta.url))
const require = createRequire(import.meta.url)

async function loadRuntime() {
	const vue = JSON.stringify(pathToFileURL(require.resolve("vue")).href)
	const modules = {
		"test-state": `export const sockets = []; export const unmounted = []; export const routers = []; export const pending = []; export const pendingComponents = []`,
		vue: `
			export * from ${vue}
			import { createRenderer } from ${vue}
			export const { createApp } = createRenderer({
				createComment: () => ({}), insert() {}, remove() {},
			})`,
		"frappe-ui": `
			import { pending, pendingComponents } from "test-state"
			export const portalTargetKey = Symbol()
			export const resourcesPlugin = { install() {} }
			export const createResource = () => ({
				fetch() { return new Promise(resolve => pending.push(data => { this.data = data; resolve(data) })) },
			})
			export const createDocumentResource = () => ({})
			export const createListResource = () => ({})
			export const dialog = {}
			export const toast = {}
			export const call = method => {
				if (method === "frappe.studio.api.get_studio_component")
					return new Promise(resolve => pendingComponents.push(resolve))
				throw new Error("unexpected request")
			}`,
		"@/socket": `
			import { sockets } from "test-state"
			export function initSocket() {
				const socket = { disconnected: false, disconnect() { this.disconnected = true } }
				sockets.push(socket)
				return socket
			}`,
		"@/router/app_router": `
			import { routers } from "test-state"
			export const createAppRouter = async () => {
				const router = { install() {} }
				routers.push(router)
				return router
			}`,
		"@/setupFrappeUIResource": "",
		"@/AppRenderer.vue": `
			import { onUnmounted } from "vue"
			import { unmounted } from "test-state"
			export default { setup() { onUnmounted(() => unmounted.push("app")); return () => null } }`,
		"@/pages/ErrorPage.vue": `
			import { onUnmounted } from "vue"
			import { unmounted } from "test-state"
			export default { props: ["error"], setup() { onUnmounted(() => unmounted.push("error")); return () => null } }`,
		dompurify: "export default {}",
		"@/browserRuntime/appRuntime":
			"export const compileComponentScript = () => null; export const compilePageScript = () => null",
	}
	const result = await build({
		configFile: false,
		logLevel: "silent",
		plugins: [
			{
				name: "mount-app-test",
				enforce: "pre",
				resolveId(id) {
					if (id in modules || id === "test-entry") return `\0${id}`
					if (id.startsWith("~icons/")) return "\0test-icon"
					if (["pinia", "vue-router", "@vueuse/core", "acorn"].includes(id))
						return { id: pathToFileURL(require.resolve(id)).href, external: true }
					if (id.startsWith("@/")) {
						const file = `${source}${id.slice(2)}`
						return [".ts", ".js", "/index.ts"].map((extension) => file + extension).find(existsSync)
					}
					if (id === pathToFileURL(require.resolve("vue")).href) return { id, external: true }
				},
				load: (id) =>
					id === "\0test-entry"
						? `export * from ${JSON.stringify(`${source}mountApp.ts`)}
							export * from "@/utils/variants"
							export * from "test-state"
							export { loadPage, useLoadedPage } from "@/page/pageLoader"
							export { default as Block } from "@/utils/block"
							export { routerKey } from "vue-router"
							export { setPageScriptImporters } from "@/data/studioPageScripts"
							export { setComponentScriptImporters } from "@/data/studioComponentScripts"
							export { createApp, nextTick } from "vue"
							export { createPinia, disposePinia } from "pinia"
							export { default as useComponentStore } from "@/stores/componentStore"
							export { default as useCodeStore } from "@/stores/codeStore"
							export { listeners as componentListeners } from "@/data/studioComponentScripts"
							export { listeners as pageListeners } from "@/data/studioPageScripts"`
						: id === "\0test-icon"
							? "export default {}"
							: modules[id.slice(1)],
				transform(code, id) {
					if (/\/data\/studio(Component|Page)Scripts\.ts$/.test(id))
						return `${code}\nexport { hotUpdateListeners as listeners }`
				},
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

test("unmount disposes stores and hot-update subscriptions while preserving the editor and supplied sockets", async () => {
	const runtime = await loadRuntime()
	const editor = runtime.createApp({ render: () => null }).use(runtime.createPinia())
	editor.provide("vueApp", editor)
	const editorStore = editor.runWithContext(() => {
		runtime.useCodeStore()
		return runtime.useComponentStore()
	})
	const editorComponentListener = [...runtime.componentListeners][0]
	const editorPageListener = [...runtime.pageListeners][0]
	let editorChanges = 0
	editorStore.$subscribe(() => editorChanges++, { flush: "sync" })
	for (const fails of [false, true]) {
		for (const kind of ["owned", "supplied", "disabled"]) {
			let store
			let pinia
			let changes = 0
			const socket = kind === "supplied" ? { disconnect: () => assert.fail("caller owns socket") } : null
			const options = {
				app: {},
				setup(vueApp) {
					pinia = vueApp.config.globalProperties.$pinia
					vueApp.runWithContext(() => {
						runtime.useCodeStore()
						store = runtime.useComponentStore()
					})
					store.$subscribe(() => changes++, { flush: "sync" })
				},
			}
			if (kind !== "owned") options.socket = socket
			if (fails)
				options.prepare = async () => {
					throw new Error("test error page")
				}
			const count = runtime.sockets.length
			const unmounted = runtime.unmounted.length
			const originalError = console.error
			let dispose
			try {
				console.error = () => {}
				dispose = await runtime.mountApp({}, options)
			} finally {
				console.error = originalError
			}
			assert.equal(runtime.sockets.length, count + (kind === "owned" ? 1 : 0))
			if (kind === "owned") assert.equal(runtime.sockets.at(-1).disconnected, false)
			assert.equal(runtime.componentListeners.size, 2)
			assert.equal(runtime.pageListeners.size, 2)
			assert.equal(pinia._s.size, 2)
			store.componentDocMap.set("before", { component_id: "before" })
			assert.equal(changes, 1)

			dispose()
			assert.equal(runtime.unmounted.length, unmounted + 1)
			assert.equal(runtime.unmounted.at(-1), fails ? "error" : "app")
			if (kind === "owned") assert.equal(runtime.sockets.at(-1).disconnected, true)
			assert.equal(pinia._s.size, 0)
			assert.deepEqual(pinia.state.value, {})
			assert.deepEqual([...runtime.componentListeners], [editorComponentListener])
			assert.deepEqual([...runtime.pageListeners], [editorPageListener])
			store.componentDocMap.set("after", { component_id: "after" })
			assert.equal(changes, 1)
			assert.equal(editorStore._p._s.get("componentStore"), editorStore)
			const previousEditorChanges = editorChanges
			editorStore.componentDocMap.set(`${fails}-${kind}`, {})
			assert.equal(editorChanges, previousEditorChanges + 1)
		}
	}
	runtime.disposePinia(editor.config.globalProperties.$pinia)
	assert.equal(runtime.componentListeners.size, 0)
	assert.equal(runtime.pageListeners.size, 0)
})

test("unmount ignores a pending page response without reviving disposed stores", async () => {
	const runtime = await loadRuntime()
	let vueApp
	let pinia
	let store
	const dispose = await runtime.mountApp(
		{},
		{
			app: {},
			setup(app) {
				vueApp = app
				pinia = app.config.globalProperties.$pinia
			},
		},
	)
	globalThis.window = {}
	try {
		const loading = vueApp.runWithContext(() => {
			store = runtime.useComponentStore()
			return runtime.loadPage(
				runtime.routers.at(-1),
				{ fullPath: "/board", meta: { appName: "app", pageName: "board" } },
				{ meta: {} },
			)
		})
		assert.equal(runtime.pending.length, 1)
		assert.equal(pinia._s.size, 1)
		dispose()
		assert.equal(pinia._s.size, 0)
		runtime.pending.pop()({
			name: "board",
			blocks: "[{}]",
			components: [{ component_id: "card" }],
		})
		await assert.doesNotReject(loading)
		assert.equal(pinia._s.size, 0)
		assert.deepEqual(pinia.state.value, {})
		assert.equal(store.componentDocMap.size, 0)
		assert.equal(runtime.componentListeners.size, 0)
		assert.equal(runtime.pageListeners.size, 0)
	} finally {
		delete globalThis.window
	}
})

async function mountTestApp(runtime) {
	let app
	const dispose = await runtime.mountApp(
		{},
		{
			app: {},
			setup(vueApp) {
				app = vueApp
			},
		},
	)
	const router = runtime.routers.at(-1)
	router.currentRoute = { value: { fullPath: "/board" } }
	app.provide(runtime.routerKey, router)
	return { app, router, pinia: app.config.globalProperties.$pinia, dispose }
}

for (const pendingScript of ["page", "component"]) {
	test(`a pending ${pendingScript} script retains its app after another mount is disposed`, async () => {
		const runtime = await loadRuntime()
		globalThis.window = {}
		const a = await mountTestApp(runtime)
		let b
		let bDisposed = false
		try {
			let resolveScript
			let scriptStarted
			const started = new Promise((resolve) => {
				scriptStarted = resolve
			})
			const loadScript = () =>
				new Promise((resolve) => {
					resolveScript = resolve
					scriptStarted()
				})
			if (pendingScript === "page") runtime.setPageScriptImporters({ board: loadScript })
			else runtime.setComponentScriptImporters({ card: loadScript })
			const to = { fullPath: "/board", meta: { appName: "a", pageName: "board" } }
			const loading = a.app.runWithContext(() => runtime.loadPage(a.router, to, { meta: {} }))
			const card = { componentName: "card", isStudioComponent: true }
			runtime.pending.pop()({
				name: "board",
				variables: [{ variable_name: "count", variable_type: "Number", initial_value: "3" }],
				resources: [],
				blocks: JSON.stringify([
					{
						componentName: "container",
						children: [card],
						componentSlots: { default: { slotName: "default", slotContent: [card] } },
					},
				]),
				components: [
					{ component_id: "card", block: JSON.stringify({ componentName: "container", children: [card] }) },
				],
			})
			await started
			b = await mountTestApp(runtime)
			b.app.runWithContext(() => runtime.useComponentStore())
			b.dispose()
			bDisposed = true
			assert.equal(b.pinia._s.size, 0)

			resolveScript({ default: pendingScript === "page" ? () => ({}) : {} })
			await assert.doesNotReject(loading)
			const { root, scope } = a.app.runWithContext(() => runtime.useLoadedPage())
			assert.equal(scope.variables.count, 3)
			assert.ok(root instanceof runtime.Block)
			assert.ok(root.children[0] instanceof runtime.Block)
			assert.ok(root.componentSlots.default.slotContent[0] instanceof runtime.Block)
			assert.ok(a.pinia._s.get("componentStore").componentMap.has("card"))
			assert.equal(b.pinia._s.size, 0)
			assert.deepEqual(b.pinia.state.value, {})
		} finally {
			runtime.setPageScriptImporters({})
			runtime.setComponentScriptImporters({})
			if (b && !bDisposed) b.dispose()
			a.dispose()
			delete globalThis.window
		}
	})
}

test("a pending component fetch deserializes in its app after another mount is disposed", async () => {
	const runtime = await loadRuntime()
	globalThis.window = {}
	const a = await mountTestApp(runtime)
	let b
	let bDisposed = false
	try {
		const store = a.app.runWithContext(() => runtime.useComponentStore())
		const loading = store.loadComponent("card")
		assert.equal(runtime.pendingComponents.length, 1)
		b = await mountTestApp(runtime)
		b.app.runWithContext(() => runtime.useComponentStore())
		b.dispose()
		bDisposed = true
		runtime.pendingComponents.pop()({
			component_id: "card",
			block: JSON.stringify({
				componentName: "container",
				children: [{ componentName: "card", isStudioComponent: true }],
			}),
		})
		await assert.doesNotReject(loading)
		assert.equal(b.pinia._s.size, 0)
		assert.deepEqual(b.pinia.state.value, {})
		assert.ok(store.componentMap.get("card") instanceof runtime.Block)
		assert.equal(store.componentMap.get("card").children[0].isStudioComponent, true)
	} finally {
		if (b && !bDisposed) b.dispose()
		a.dispose()
		delete globalThis.window
	}
})

test("default slots retain their canvas store across the deferred selection", async () => {
	const runtime = await loadRuntime()
	const a = await mountTestApp(runtime)
	const b = await mountTestApp(runtime)
	try {
		b.app.runWithContext(() => runtime.useComponentStore())
		b.dispose()
		runtime.Block.setComponents({ container: { initialSlots: ["default"] } })
		const block = a.app.runWithContext(() => new runtime.Block({ componentName: "container" }))
		await runtime.nextTick()
		assert.equal(block.componentSlots.default.slotName, "default")
		assert.ok(a.pinia._s.has("canvasStore"))
		assert.equal(b.pinia._s.size, 0)
		assert.deepEqual(b.pinia.state.value, {})
	} finally {
		runtime.Block.setComponents({})
		a.dispose()
	}
})

test("variant sets and tokens belong to each mount", async () => {
	const runtime = await loadRuntime()
	const a = await mountTestApp(runtime)
	const b = await mountTestApp(runtime)
	const register = (mount, blockId) =>
		mount.app.runWithContext(() => {
			runtime.retainVariantSet(blockId)
			return runtime.registerVariantSet({ blockId, name: "Theme", options: ["Light", "Dark"], optionIds: [] })
		})
	try {
		const setsA = a.app.runWithContext(() => runtime.useMountedVariantSets())
		const setsB = b.app.runWithContext(() => runtime.useMountedVariantSets())
		const first = register(a, "first")
		const second = register(b, "second")
		assert.equal(first.token, "theme")
		assert.equal(second.token, "theme")
		assert.deepEqual(
			setsA.value.map((set) => set.blockId),
			["first"],
		)
		assert.deepEqual(
			setsB.value.map((set) => set.blockId),
			["second"],
		)
		register(a, "second")
		a.app.runWithContext(() => runtime.releaseVariantSet("second"))
		assert.deepEqual(
			setsB.value.map((set) => set.blockId),
			["second"],
		)
		a.app.runWithContext(() => runtime.releaseVariantSet("first"))
		assert.equal(setsA.value.length, 0)
		assert.equal(register(a, "third").token, "theme")
	} finally {
		a.dispose()
		b.dispose()
	}
})
