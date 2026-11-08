/**
 * @type {{
 *   name: string
 *   files: Record<string, string>
 *   expected?: unknown
 *   failureContains?: string
 *   previewOnly?: boolean
 * }[]}
 *
 * `previewOnly` documents a remaining difference in the browser's CommonJS loader.
 */
export const moduleFixtures = [
	{
		name: "default-named-and-namespace",
		files: {
			"value.js": "export default 7; export const value = 3",
			"entry.js": `import main, { value } from "./value.js"; import * as all from "./value.js";
export const run = () => [main, value, all.default, all.value, Object.keys(all).sort()]`,
		},
		expected: [7, 3, 7, 3, ["default", "value"]],
	},
	{
		name: "destructured-exports",
		files: {
			"value.js": "export const { two, three } = { two: 2, three: 3 }",
			"entry.js": "import { two, three } from './value.js'; export const run = () => two + three",
		},
		expected: 5,
	},
	{
		name: "paths-and-comments",
		files: {
			"utils/index.js": "export const value = 3",
			"entry.js": `import { value } from "@app/utils"; // import "./missing.js"
const text = 'import "./missing.js"'; export const run = () => [value, text.length > 0]`,
		},
		expected: [3, true],
	},
	{
		name: "reexports-and-live-bindings",
		files: {
			"state.js": "export let count = 0; export function add() { count++ }; export default 'default'",
			"barrel.js": `export * from "./state.js"; export { default as label } from "./state.js"; export * as state from "./state.js"`,
			"entry.js": `import { count, add, label, state } from "./barrel.js";
export function run() { const before = count; add(); return [before, count, state.count, label] }`,
		},
		expected: [0, 1, 1, "default"],
	},
	{
		name: "diamond-reexports",
		files: {
			"base.js": "export const value = 42",
			"left.js": "export { value } from './base.js'",
			"right.js": "import { value } from './base.js'; export { value }",
			"barrel.js": "export * from './left.js'; export * from './right.js'",
			"entry.js": "import { value } from './barrel.js'; export const run = () => value",
		},
		expected: 42,
	},
	{
		name: "explicit-export-overrides-star",
		files: {
			"a.js": "export const value = 1",
			"b.js": "export const value = 2",
			"barrel.js": "export * from './a.js'; export * from './b.js'; export {value} from './a.js'",
			"entry.js": "import { value } from './barrel.js'; export const run = () => value",
		},
		expected: 1,
	},
	{
		name: "deferred-cycle",
		files: {
			"a.js": "import {readA} from './b.js'; export const a = 'a'; export const read = () => readA()",
			"b.js": "import {a} from './a.js'; export const readA = () => a",
			"entry.js": "import { read } from './a.js'; export const run = () => read()",
		},
		expected: "a",
	},
	{
		name: "side-effects-once-and-in-order",
		files: {
			"base.js": "globalThis.__moduleFixtureOrder.push('base')",
			"left.js": "import './base.js'; globalThis.__moduleFixtureOrder.push('left')",
			"right.js": "import './base.js'; globalThis.__moduleFixtureOrder.push('right')",
			"entry.js":
				"import './left.js'; import './right.js'; export const run = () => globalThis.__moduleFixtureOrder.slice()",
		},
		expected: ["base", "left", "right"],
	},
	{
		name: "lazy-local-module",
		files: {
			"lazy.js": "globalThis.__moduleFixtureOrder.push('lazy'); export const value = 42",
			"entry.js": `export async function run() { const before = globalThis.__moduleFixtureOrder.length;
const first = await import('./lazy.js'); const second = await import('./lazy.js');
return [before, first.value, first === second, globalThis.__moduleFixtureOrder.length] }`,
		},
		expected: [0, 42, true, 1],
	},
	{
		name: "json-exports",
		files: {
			"theme.json": '{"accent":"teal","size":3}',
			"entry.js":
				"import theme, { accent, size } from './theme.json'; export const run = () => [theme, accent, size]",
		},
		expected: [{ accent: "teal", size: 3 }, "teal", 3],
	},
	{
		name: "css-side-effect",
		files: {
			"theme.css": ".studio-module-fixture { color: rgb(1, 2, 3) }",
			"entry.js": `import './theme.css'; import '@app/theme.css'; import * as styles from '@app/theme.css';
export function run() { const el = document.createElement('div');
el.className = 'studio-module-fixture'; document.body.append(el); const color = getComputedStyle(el).color; el.remove();
return [color, Object.keys(styles), document.querySelectorAll('style[data-studio-app-css="theme.css"]').length] }`,
		},
		expected: ["rgb(1, 2, 3)", [], 1],
	},
	{
		name: "external-reexports",
		files: {
			"barrel.js": "export {ref} from 'vue'; export * as Vue from 'vue'",
			"entry.js":
				"import {ref, Vue} from './barrel.js'; export const run = () => [ref === Vue.ref, Vue.isRef(ref(42))]",
		},
		expected: [true, true],
	},
	{
		name: "external-star-reexport",
		files: {
			"barrel.js": "export * from 'vue'",
			"entry.js": "import { ref, isRef } from './barrel.js'; export const run = () => isRef(ref(42))",
		},
		expected: true,
	},
	{
		name: "vue-instance-and-lifecycle",
		files: {
			"entry.js": `import {createApp, h, ref, watch, nextTick, onMounted, onUnmounted} from 'vue'; import {Button} from 'frappe-ui';
export async function run() { const source = ref(0); let mounted = 0, unmounted = 0, watched = 0, clicks = 0;
const root = document.createElement('div'); document.body.append(root);
const app = createApp({setup() { onMounted(() => mounted++); onUnmounted(() => unmounted++);
watch(source, () => watched++); return () => h(Button, {label:'Save', onClick:() => clicks++}) }});
app.mount(root); root.querySelector('button').click(); source.value++; await nextTick(); app.unmount();
source.value++; await nextTick(); root.remove(); return {mounted, unmounted, watched, clicks} }`,
		},
		expected: { mounted: 1, unmounted: 1, watched: 1, clicks: 1 },
	},
	{
		name: "module-and-function-this",
		files: {
			"value.js": "export function receiver() { return this }",
			"entry.js":
				"import {receiver} from './value.js'; const top = this; export const run = () => [top === undefined, receiver() === undefined]",
		},
		expected: [true, true],
	},
	{
		name: "function-local-commonjs-names",
		files: {
			"entry.js":
				"export function run() { const module = 1, exports = 2; const require = () => 3; return module + exports + require() }",
		},
		expected: 6,
	},
	{
		name: "default-through-barrel",
		files: {
			"base.js": "export default 42",
			"barrel.js": "export { default } from './base.js'",
			"entry.js": "import value from './barrel.js'; export const run = () => value",
		},
		expected: 42,
	},
	{
		name: "json-namespace",
		files: {
			"theme.json": '{"accent":"teal","size":3}',
			"entry.js": "import * as theme from './theme.json'; export const run = () => Object.keys(theme).sort()",
		},
		expected: ["accent", "default", "size"],
	},
	{
		name: "json-string-named-import",
		files: {
			"theme.json": '{"foo-bar":"teal"}',
			"entry.js": `import {"foo-bar" as accent} from './theme.json'; export const run = () => accent`,
		},
		failureContains: "String-named imports",
	},
	{
		name: "modern-class-field-semantics",
		files: {
			"entry.js":
				"class Base { set value(v) { throw new Error('setter invoked') } }; class Child extends Base { value = 3 }; export const run = () => new Child().value",
		},
		expected: 3,
	},
	{
		name: "async-function-await",
		files: { "entry.js": "export async function run() { return await Promise.resolve(42) }" },
		expected: 42,
	},
	...[
		[
			"missing-named-import",
			"import { two } from './value.js'; export const run = () => two",
			"export const one = 1",
			'"value.js" has no export named "two"',
		],
		[
			"missing-default",
			"import value from './value.js'; export const run = () => value",
			"export const value = 1",
			"default",
		],
		[
			"import-escapes-the-app",
			'import value from "@app/../outside.js"; export const run = () => value',
			"export const value = 1",
			"Cannot resolve",
		],
		[
			"missing-default-reexport",
			"export {default as run} from './value.js'",
			"export const value = 1",
			"default",
		],
		[
			"missing-named-reexport",
			"export {missing as run} from './value.js'",
			"export const value = 1",
			"missing",
		],
		[
			"missing-through-barrel",
			"import value from './value.js'; export const run = () => value",
			"export * from './base.js'",
			"default",
			{ "base.js": "export default 1" },
		],
		["missing-external-default", "import Vue from 'vue'; export const run = () => Vue", "", "default"],
		["missing-external-reexport", "export {missing as run} from 'vue'", "", "missing"],
		[
			"missing-json-name",
			"import {missing} from './value.json'; export const run = () => missing",
			"",
			"missing",
			{ "value.json": "{}" },
		],
		[
			"css-has-no-default",
			"import css from './value.css'; export const run = () => css",
			"",
			"default",
			{ "value.css": ".fixture {color:red}" },
		],
	].map(([name, entry, value, failureContains, extra = {}]) => ({
		name,
		files: { "entry.js": entry, "value.js": value, ...extra },
		failureContains,
	})),
	{
		name: "ambiguous-star-import",
		files: {
			"a.js": "export const value = 1",
			"b.js": "export const value = 2",
			"barrel.js": "export * from './a.js'; export * from './b.js'",
			"entry.js": "import {value} from './barrel.js'; export const run = () => value",
		},
		failureContains: "value",
	},
	...[
		["commonjs-require", "export const run = () => require('./value.js')", "require", { "value.js": "" }],
		["commonjs-module", "module.exports = {run:() => 1}", "module"],
		["commonjs-exports", "exports.run = () => 1", "exports"],
		["top-level-reserved-name", "const module = 1; export const run = () => module", "reserved"],
		["computed-import", "export const run = name => import('./' + name)", "literal module path"],
		["string-named-export", "const value = 1; export {value as 'foo-bar'}", "String-named imports"],
		["import-meta", "export const run = () => import.meta.env.MODE", "import.meta"],
		[
			"unsupported-library",
			"import {useDebounceFn} from '@vueuse/core'; export const run = () => useDebounceFn",
			"not importable",
		],
		[
			"import-query",
			"import text from './value.js?raw'; export const run = () => text",
			"Import queries",
			{ "value.js": "export default 1" },
		],
		[
			"import-attributes",
			"export const run = () => import('./theme.json', {with:{type:'json'}})",
			"Import attributes",
			{ "theme.json": "{}" },
		],
	].map(([name, entry, failureContains, extra = {}]) => ({
		name,
		files: { "entry.js": entry, ...extra },
		failureContains,
	})),
	// Sucrase passes these through, so the loader reports what new Function() rejects.
	...[["top-level-await", "export const run = await Promise.resolve(() => 1)", "await is only valid"]].map(
		([name, entry, failureContains]) => ({
			name,
			files: { "entry.js": entry },
			failureContains,
			previewOnly: true,
		}),
	),
]
