import { readFile } from "node:fs/promises";

import { compileScript, parse } from "vue/compiler-sfc";

// Compiles the page and the core screens it composes for DOM tests. Every other .vue
// file is a shallow stub carrying its name, and the modules that reach the site are
// fakes the tests drive. Run with --preserve-symlinks so the linked core resolves this
// app's Vue rather than its own copy.
const vue = import.meta.resolve("vue");
const moduleURL = (code) => `data:text/javascript;base64,${Buffer.from(code).toString("base64")}`;

const real = new Set([
	"FlowPage.vue",
	"RecordPage.vue",
	"RecordList.vue",
	"RecordForm.vue",
	"PageHeader.vue",
	"AgentPicker.vue",
	"AgentPalette.vue",
	"SkillPicker.vue",
	"SessionSidebar.vue",
	"ChatHeader.vue",
	"ChatMenu.vue",
	"ShareChat.vue",
	"MessageList.vue",
	"LoadingState.vue",
	"Composer.vue",
	"ModelButton.vue",
	"DocPanel.vue",
	"FieldControl.vue",
	"CodeField.vue",
	"SettingsPage.vue",
	"RecordTable.vue",
	"ValueView.vue",
	"CreateView.vue",
	"ReadView.vue",
	"NamesView.vue",
	"CodeView.vue",
	"SnippetView.vue",
	"JsonView.vue",
	"CodeBlock.vue",
]);
const stubs = new Map();
function stubURL(name) {
	if (!stubs.has(name))
		stubs.set(
			name,
			moduleURL(`
				import { h } from ${JSON.stringify(vue)}
				export default { render() { return h("div", { "data-stub": ${JSON.stringify(
					name
				)} }, this.$slots.default?.({})) } }
			`)
		);
	return stubs.get(name);
}

const fakes = {
	"frappe-ui": moduleURL(`
		import { h } from ${JSON.stringify(vue)}
		const stub = (name) => ({ render() { return h("div", { "data-stub": name }) } })
		export const Dialogs = stub("Dialogs")
		export const ToastProvider = stub("ToastProvider")
		export const Badge = stub("Badge")
		export const FormLabel = stub("FormLabel")
		export const FileUploader = stub("FileUploader")
		export const Switch = stub("Switch")
		export const ErrorMessage = { props: ["message"], render() { return h("p", this.message) } }
		export const Avatar = stub("Avatar")
		export const Dialog = {
			props: ["open", "title"],
			render() { return this.open ? h("div", { role: "dialog", "aria-label": this.title }, [this.$slots.default?.(), this.$slots.actions?.()]) : null }
		}
		export const Select = {
			props: ["modelValue", "options"],
			emits: ["update:modelValue"],
			render() { return h("div", { "data-control": "select", "data-value": this.modelValue }, (this.options || []).map(o => h("button", { onClick: () => this.$emit("update:modelValue", o.value) }, o.label))) }
		}
		export const Button = {
			props: ["label", "loading"],
			render() { return h("button", { disabled: this.loading }, this.label) }
		}
		export const FormControl = {
			props: ["modelValue", "options", "query", "type", "label", "filterable", "loading"],
			emits: ["update:modelValue", "update:query"],
			render() {
				const remote = ["combobox", "multiselect"].includes(this.type)
				// like frappe-ui's combobox, a loading control shows no options
				const options = this.loading ? [] : this.options || []
				return h("div", { "data-control": this.label || this.type }, [
					h("input", { value: remote ? this.query : this.modelValue, onInput: e => this.$emit(remote ? "update:query" : "update:modelValue", e.target.value) }),
					...options.map(o => h("button", { onClick: () => this.$emit("update:modelValue", o.value) }, o.label)),
				])
			}
		}
		export const toast = { shown: [], success(message) { this.shown.push(message) }, error() {} }
		export const dialog = {
			asked: [],
			danger(options) { this.asked.push(options) },
			prompt() {},
			confirm(options) { this.asked.push(options) },
		}
		export function useColorScheme() {}
	`),
	// the core's menus: the trigger, and the options once it is clicked or held open
	"frappe-ui/src/components/Dropdown/Dropdown.vue": moduleURL(`
		import { h, ref } from ${JSON.stringify(vue)}
		export default {
			props: ["options", "open"],
			setup(props, { slots }) {
				const shown = ref(false)
				return () => h("div", { "data-stub": "Dropdown" }, [
					h("div", { onClick: () => (shown.value = !shown.value) }, slots.trigger?.()),
					...((props.open ?? shown.value) ? props.options ?? [] : []).map((o) =>
						h("button", { role: "menuitem", onClick: o.onClick }, o.label)),
				])
			},
		}
	`),
	"frappe-ui/code-editor": moduleURL(`
		export const CodeEditor = { render() { return null } }
		export const CodeEditorContent = { render() { return null } }
		export const CodeKit = { configure() { return [] } }
	`),
	"frappe-ui/src/utils/dialog": moduleURL(`
		import { ref } from ${JSON.stringify(vue)}
		export const dialogs = ref([])
		export const dialog = {}
	`),
	"../api/frappe.js": moduleURL(`
		export const calls = []
		export const answers = {}
		export async function call(method, args = {}) {
			calls.push([method, args])
			if (!(method in answers)) throw new Error("unexpected call: " + method)
			const answer = answers[method]
			return typeof answer === "function" ? answer(args) : answer
		}
		export async function uploadFile() { throw new Error("no uploads here") }
		export function deleteFile() {}
	`),
	"../api/socket.js": moduleURL(`
		export const socket = {
			on() {}, off() {}, disconnect() {},
			emit(name, ...args) {
				const ack = args.at(-1)
				if (name === "flow:subscribe" && typeof ack === "function") ack({ subscribed: true })
			},
		}
		export function connectSocket() { return socket }
	`),
};
export const transport = await import(fakes["../api/frappe.js"]);
export const { toast, dialog } = await import(fakes["frappe-ui"]);

const compiled = new Map();
async function componentURL(url) {
	if (compiled.has(url.href)) return compiled.get(url.href);
	const source = await readFile(url, "utf8");
	let content = source;
	if (url.pathname.endsWith(".vue")) {
		const { descriptor } = parse(source, { filename: url.pathname });
		content = compileScript(descriptor, { id: url.pathname, inlineTemplate: true }).content;
	}
	// static imports and lazy import("…") calls
	const imports = [...content.matchAll(/\b(from\s+|import\(\s*)["']([^"']+)["']/g)];
	for (const match of imports.reverse()) {
		const specifier = match[2];
		let resolved;
		if (specifier in fakes) resolved = fakes[specifier];
		else if (specifier.endsWith(".vue")) {
			const name = specifier.split("/").pop();
			resolved = real.has(name)
				? await componentURL(targetURL(specifier, url))
				: stubURL(name.slice(0, -4));
		} else if (specifier.startsWith("."))
			// a relative module of this app: compile it too, so its own .vue imports resolve
			resolved = await componentURL(targetURL(specifier, url));
		else resolved = targetURL(specifier, url).href;
		content =
			content.slice(0, match.index) +
			`${match[1]}${JSON.stringify(resolved)}` +
			content.slice(match.index + match[0].length);
	}
	const result = moduleURL(content);
	compiled.set(url.href, result);
	return result;
}

const targetURL = (specifier, from) =>
	specifier.startsWith(".") ? new URL(specifier, from) : new URL(import.meta.resolve(specifier));

export async function loadComponent(path) {
	return (await loadModule(path)).default;
}

export async function loadModule(path) {
	const url = new URL(`../../src/${path}`, import.meta.url);
	return await import(await componentURL(url));
}
