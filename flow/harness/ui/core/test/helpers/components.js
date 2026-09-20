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
// frappe-ui's settings pieces as slot-rendering stubs that keep their tab value
const settingsPieces = moduleURL(`
	import { h } from ${JSON.stringify(vue)}
	const piece = (name, tag = "div") => ({
		props: ["value", "open", "tab", "size", "shortcut"],
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
	export const Button = {
		props: ["label", "disabled"],
		render() {
			return h("button", { disabled: this.disabled }, this.label)
		},
	}
`)
const components = new Set([
	"Composer.vue", "ToolStep.vue", "ToolGroup.vue", "ApprovalCard.vue", "MessageList.vue", "ModelButton.vue", "PopMenu.vue",
	"SettingsDialog.vue", "SettingsPage.vue", "UserBubble.vue", "TurnFold.vue", "ThinkingBlock.vue", "ThoughtStep.vue",
	"SubagentView.vue",
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
		if (specifier.endsWith(".vue")) {
			const name = specifier.split("/").pop()
			resolved = components.has(name) ? await componentURL(new URL(specifier, url)) : stubURL(name.slice(0, -4))
		} else if (specifier === "frappe-ui/src/utils/dialog") {
			resolved = dialogs
		} else if (specifier === "frappe-ui/src/components/SettingsDialog") {
			resolved = settingsPieces
		} else if (specifier.startsWith("frappe-ui/src/components/")) {
			resolved = widgets
		} else {
			resolved = specifier.startsWith(".") ? new URL(specifier, url).href : import.meta.resolve(specifier)
		}
		content = content.slice(0, match.index) + `from ${JSON.stringify(resolved)}` + content.slice(match.index + match[0].length)
	}
	const result = moduleURL(content)
	compiled.set(url.href, result)
	return result
}

export async function loadComponent(name) {
	const url = new URL(`../../src/components/${name}.vue`, import.meta.url)
	return (await import(await componentURL(url))).default
}
