import { readFile } from "node:fs/promises"

import { compileScript, parse } from "vue/compiler-sfc"

const vue = import.meta.resolve("vue")
const moduleURL = (code) => `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`
const stubs = new Map()
// a stub carries its name so a test can see which widget the tree mounted
function stubURL(name) {
	if (!stubs.has(name))
		stubs.set(name, moduleURL(`
			import { h } from ${JSON.stringify(vue)}
			export default { render() { return h('div', { 'data-stub': ${JSON.stringify(name)} }, this.$slots.default?.()) } }
		`))
	return stubs.get(name)
}
const dialogs = moduleURL(`import { ref } from ${JSON.stringify(vue)}; export const dialogs = ref([]); export const dialog = {}`)
// a test sets the dialog.* calls it expects, or opens one on the stack
export const { dialog, dialogs: dialogStack } = await import(dialogs)
// frappe-ui's Dropdown as its trigger, and its options, groups flattened, once it is clicked or held open
const dropdown = moduleURL(`
	import { h, ref } from ${JSON.stringify(vue)}
	export default {
		props: ["options", "open"],
		setup(props, { slots }) {
			const shown = ref(false)
			return () => h("div", { "data-stub": "Dropdown" }, [
				h("div", { onClick: () => (shown.value = !shown.value) }, slots.trigger?.()),
				...((props.open ?? shown.value) ? props.options ?? [] : []).flatMap((o) => o.options ?? [o]).map((o) =>
					h("button", { role: "menuitem", onClick: o.onClick }, o.label)),
			])
		},
	}
`)
// frappe-ui's SidebarItem split as it is: the row takes class, style and listeners, its button the
// click and every other attribute, and the suffix sits beside the button, outside its click
const sidebarItem = moduleURL(`
	import { h } from ${JSON.stringify(vue)}
	export default {
		inheritAttrs: false,
		props: ["active", "label", "icon", "onClick"],
		setup(props, { attrs, slots }) {
			const rowAttr = (key) => key === "class" || key === "style" || /^on[A-Z]/.test(key)
			const split = (row) => Object.fromEntries(Object.entries(attrs).filter(([key]) => rowAttr(key) === row))
			return () => h("div", { "data-stub": "SidebarItem", ...split(true) }, [
				h("button", { type: "button", ...split(false), onClick: props.onClick }, [slots.prefix?.(), slots.default?.()]),
				slots.suffix?.(),
			])
		},
	}
`)
// frappe-ui's HoverCard as its trigger, and its card while open; a hover asks to open or close it
const hoverCard = moduleURL(`
	import { h } from ${JSON.stringify(vue)}
	export default {
		props: ["open"],
		emits: ["update:open"],
		setup(props, { slots, emit }) {
			return () => h("div", {
				"data-stub": "HoverCard",
				onPointerenter: () => emit("update:open", true),
				onPointerleave: () => emit("update:open", false),
			}, [slots.trigger?.(), props.open ? h("div", { "data-card": "" }, slots.default?.()) : null])
		},
	}
`)
// reka's dialog pieces: the root shows its content while open, and its close asks it to close
const reka = moduleURL(`
	import { h, inject, provide } from ${JSON.stringify(vue)}
	const close = Symbol("close")
	export const DialogRoot = {
		props: ["open"],
		emits: ["update:open"],
		setup(props, { slots, emit }) {
			provide(close, () => emit("update:open", false))
			return () => (props.open ? slots.default?.() : null)
		},
	}
	export const DialogPortal = { setup: (props, { slots }) => () => slots.default?.() }
	export const DialogContent = { setup: (props, { slots }) => () => h("div", { role: "dialog" }, slots.default?.()) }
	export const DialogTitle = { props: ["as"], setup: (props, { slots }) => () => h(props.as ?? "h2", slots.default?.()) }
	export const DialogClose = {
		setup(props, { slots }) {
			const done = inject(close)
			return () => h("button", { onClick: done }, slots.default?.())
		},
	}
`)
// monaco can't run under jsdom: the editor's lazy import gets the test's fake instead
const monaco = moduleURL("export const monaco = globalThis.monaco")
// frappe-ui's color scheme as a plain ref: Node won't strip the types of its TypeScript in node_modules
const colorScheme = moduleURL(`
	import { ref } from ${JSON.stringify(vue)}
	const colorScheme = ref("system")
	export const useColorScheme = () => ({ colorScheme, setColorScheme: (scheme) => (colorScheme.value = scheme) })
`)
// the web app's one import of the core package, minus the .vue files Node can't load
const uiCore = moduleURL(`
	export { DaemonClient } from ${JSON.stringify(new URL("../../src/client.js", import.meta.url).href)}
	export { createFlowStore } from ${JSON.stringify(new URL("../../src/store.js", import.meta.url).href)}
	export { default as FlowChat } from ${JSON.stringify(stubURL("FlowChat"))}
	export { default as LoadingState } from ${JSON.stringify(stubURL("LoadingState"))}
`)
// frappe-ui's settings pieces as slot-rendering stubs that keep their tab value
const settingsPieces = moduleURL(`
	import { h } from ${JSON.stringify(vue)}
	const piece = (name, tag = "div") => ({
		props: ["value", "open", "tab", "size", "keyboardShortcut"],
		render() {
			return h(tag, { "data-stub": name, "data-value": this.value }, [this.$slots.label?.(), this.$slots.prefix?.(), this.$slots.default?.()])
		},
	})
	export const SettingsDialog = piece("SettingsDialog")
	export const SettingsSidebar = piece("SettingsSidebar")
	export const SettingsNavGroup = piece("SettingsNavGroup")
	export const SettingsNavItem = piece("SettingsNavItem", "button")
	export const SettingsContent = piece("SettingsContent")
	export const SettingsPanel = piece("SettingsPanel")
`)
// frappe-ui form widgets as bare inputs: enough to tick, type and click in a test
const widgets = moduleURL(`
	import { h } from ${JSON.stringify(vue)}
	const text = (tag) => ({
		props: ["modelValue"],
		emits: ["update:modelValue"],
		render() {
			return h(tag, { value: this.modelValue, onInput: (e) => this.$emit("update:modelValue", e.target.value) })
		},
	})
	export const TextInput = text("input")
	export const Textarea = text("textarea")
	export const Checkbox = {
		props: ["modelValue", "disabled"],
		emits: ["update:modelValue"],
		render() {
			return h("input", {
				type: "checkbox",
				checked: this.modelValue,
				disabled: this.disabled,
				onChange: (e) => this.$emit("update:modelValue", e.target.checked),
			})
		},
	}
	export const Badge = {
		props: ["label", "theme", "variant", "size"],
		render() {
			return h("span", { "data-stub": "Badge" }, this.$slots.default?.() ?? this.label)
		},
	}
	export const Button = {
		props: ["label", "disabled"],
		render() {
			return h("button", { disabled: this.disabled }, this.label)
		},
	}
	export const Select = { ...text("select"), props: ["modelValue", "options"] }
`)
const components = new Set([
	"Composer.vue", "ToolStep.vue", "ToolGroup.vue", "ApprovalCard.vue", "MessageList.vue", "ModelButton.vue",
	"SettingsDialog.vue", "SettingsPage.vue", "UserBubble.vue", "TurnFold.vue", "ThinkingBlock.vue", "ThoughtStep.vue",
	"SubagentView.vue", "TranscriptDialog.vue", "WorkspacePanel.vue", "FilesBar.vue", "FileTree.vue", "LoadingState.vue", "AddToChat.vue",
	"EditorView.vue", "ChatMenu.vue", "PresetButton.vue", "SuggestedReplies.vue",
])
const compiled = new Map()

// Compile the real templates for DOM tests; unrelated child widgets are shallow
// stubs. File URLs keep normal JS imports on Node's shared module/Vue instance.
async function componentURL(url) {
	if (compiled.has(url.href)) return compiled.get(url.href)
	const source = await readFile(url, "utf8")
	const { descriptor } = parse(source, { filename: url.pathname })
	let { content } = compileScript(descriptor, { id: url.pathname, inlineTemplate: true })
	const imports = [...content.matchAll(/\bfrom\s+["']([^"']+)["']/g)]
	for (const match of imports.reverse()) {
		const specifier = match[1]
		let resolved
		if (specifier === "frappe-ui/src/components/Dropdown/Dropdown.vue") {
			resolved = dropdown
		} else if (specifier === "frappe-ui/src/components/HoverCard/HoverCard.vue") {
			resolved = hoverCard
		} else if (specifier === "reka-ui") {
			resolved = reka
		} else if (specifier === "frappe-ui/src/components/Sidebar/SidebarItem.vue") {
			resolved = sidebarItem
		} else if (specifier.endsWith(".vue")) {
			const name = specifier.split("/").pop()
			resolved = components.has(name) ? await componentURL(new URL(specifier, url)) : stubURL(name.slice(0, -4))
		} else if (specifier === "frappe-ui/src/utils/dialog") {
			resolved = dialogs
		} else if (specifier === "frappe-ui/src/composables/useColorScheme") {
			resolved = colorScheme
		} else if (specifier === "frappe-ui/src/components/SettingsDialog") {
			resolved = settingsPieces
		} else if (specifier.startsWith("frappe-ui/src/components/")) {
			resolved = widgets
		} else if (specifier === "@flow/ui-core") {
			resolved = uiCore
		} else {
			resolved = specifier.startsWith(".") ? new URL(specifier, url).href : import.meta.resolve(specifier)
		}
		content = content.slice(0, match.index) + `from ${JSON.stringify(resolved)}` + content.slice(match.index + match[0].length)
	}
	content = content.replaceAll('import("../monaco.js")', `import(${JSON.stringify(monaco)})`)
	const result = moduleURL(content)
	compiled.set(url.href, result)
	return result
}

export async function loadComponent(name, url = new URL(`../../src/components/${name}.vue`, import.meta.url)) {
	return (await import(await componentURL(url))).default
}
