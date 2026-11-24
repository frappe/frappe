import assert from "node:assert/strict"
import { createRequire } from "node:module"
import test from "node:test"
import { fileURLToPath, pathToFileURL } from "node:url"
import vue from "@vitejs/plugin-vue"
import { build } from "vite"

const source = fileURLToPath(new URL("../../src/", import.meta.url))
const require = createRequire(import.meta.url)

async function loadRuntime() {
	const vueUrl = JSON.stringify(pathToFileURL(require.resolve("vue")).href)
	const modules = {
		vue: `
			export * from ${vueUrl}
			import { createRenderer } from ${vueUrl}
			export const { createApp } = createRenderer({
				createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
				setText() {}, setElementText() {}, insert() {}, remove() {}, patchProp() {},
				parentNode: () => null, nextSibling: () => null,
			})`,
		"@/AppRenderer.vue": `
			import { inject } from "vue"
			export default { setup() { inject("reportTitle")("Board"); return () => null } }`,
	}
	const result = await build({
		configFile: false,
		logLevel: "silent",
		plugins: [
			vue(),
			{
				name: "studio-island-test",
				enforce: "pre",
				resolveId(id) {
					if (id in modules || id === "test-entry") return `\0${id}`
					if (id === "vue-router") return { id: pathToFileURL(require.resolve(id)).href, external: true }
					if (id === pathToFileURL(require.resolve("vue")).href) return { id, external: true }
					if (id === "@/utils/islandRoute") return `${source}utils/islandRoute.ts`
				},
				load: (id) =>
					id === "\0test-entry"
						? `export { default as StudioIsland } from ${JSON.stringify(`${source}StudioIsland.vue`)}
							export { islandPath } from "@/utils/islandRoute"
							export { createApp, h, shallowRef } from "vue"`
						: modules[id.slice(1)],
			},
		],
		build: {
			write: false,
			minify: false,
			rolldownOptions: { input: "test-entry", preserveEntrySignatures: "strict" },
		},
	})
	const runtime = await import(
		`data:text/javascript;base64,${Buffer.from(result.output[0].code).toString("base64")}`
	)
	const router = await import(pathToFileURL(require.resolve("vue-router")).href)
	return { ...runtime, ...router }
}

async function mountIsland(runtime, initialProps) {
	const history = runtime.createMemoryHistory()
	history.replace(runtime.islandPath(initialProps))
	const router = runtime.createRouter({
		history,
		routes: [
			{ path: "/", redirect: "/board" },
			{ path: "/:page", component: { render: () => null } },
		],
	})
	const events = { title: [], route: [] }
	const props = runtime.shallowRef({
		...initialProps,
		onTitle: (title) => events.title.push(title),
		onRoute: (route, query) => events.route.push([route, query]),
	})
	const app = runtime.createApp({ render: () => runtime.h(runtime.StudioIsland, props.value) })
	app.use(router)
	app.mount({})
	await router.push(history.location)
	const update = async (next) => {
		props.value = { ...props.value, ...next }
		await new Promise((resolve) => setTimeout(resolve))
	}
	return { app, router, events, update }
}

test("islandPath joins the route below the page and its query", async () => {
	const { islandPath } = await loadRuntime()
	assert.equal(islandPath({}), "/")
	assert.equal(islandPath({ route: ["orders"], query: { status: "Draft" } }), "/orders?status=Draft")
})

test("the island reports its title and its own navigation, never its first route", async () => {
	const runtime = await loadRuntime()
	const { router, events, app } = await mountIsland(runtime, { route: [], query: {} })

	assert.equal(router.currentRoute.value.path, "/board")
	assert.deepEqual(events.title, ["Board"])
	assert.deepEqual(events.route, [])

	await router.push("/customers?tab=open")
	assert.deepEqual(events.route, [[["customers"], { tab: "open" }]])

	app.unmount()
	await router.push("/board")
	assert.equal(events.route.length, 1)
})

test("the island starts at the route it is given and follows route updates", async () => {
	const runtime = await loadRuntime()
	const { router, app, update } = await mountIsland(runtime, { route: ["customers"], query: {} })
	assert.equal(router.currentRoute.value.path, "/customers")

	await update({ route: ["board"], query: { range: "week" } })
	assert.equal(router.currentRoute.value.fullPath, "/board?range=week")
	app.unmount()
})

test("an encoded segment, repeated query and flag survive a host route round-trip", async () => {
	const runtime = await loadRuntime()
	const { router, events, app, update } = await mountIsland(runtime, { route: ["board"] })
	await router.push("/orders/a%2Fb?tag=a&tag=b&flag")
	const [route, query] = events.route.at(-1)
	assert.deepEqual(route, ["orders", "a/b"])
	assert.deepEqual(query, { tag: ["a", "b"], flag: null })
	await update({ route, query })
	assert.equal(router.currentRoute.value.fullPath, "/orders/a%2Fb?tag=a&tag=b&flag")
	app.unmount()
})
