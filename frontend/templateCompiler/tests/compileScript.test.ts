// @vitest-environment node
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { afterAll, describe, expect, it } from "vitest";
import { compileTemplate } from "vue/compiler-sfc";
import { createSSRApp } from "vue";
import { renderToString } from "vue/server-renderer";
import { cacheKeyParts, compileScript } from "../compileScript.mjs";

const folder = path.dirname(fileURLToPath(import.meta.url));
const scratch = path.join(folder, "../../node_modules/.template-compiler-test");

afterAll(() => fs.rmSync(scratch, { recursive: true, force: true }));

function component(body: string) {
	return `export default {\n${body}\n}\n`;
}

function errorsOf(source: string) {
	const result = compileScript(source);
	expect(result.code).toBeNull();
	return result.errors;
}

async function render(source: string, props = {}) {
	const { code } = compileScript(source);
	fs.mkdirSync(scratch, { recursive: true });
	const file = path.join(scratch, `${Math.random().toString(36).slice(2)}.mjs`);
	fs.writeFileSync(file, code);
	const module = await import(/* @vite-ignore */ pathToFileURL(file).href);
	return renderToString(createSSRApp(module.default, props));
}

describe("which keys are templates", () => {
	it("passes a file with no template: through unchanged", () => {
		const source = "export default { onRefresh(page) {} }\n";
		expect(compileScript(source)).toEqual({ code: source, errors: [] });
	});

	it("keeps a quoted template: key as plain data", () => {
		const source = 'frappe.call({ args: { "template": name } })\n';
		expect(compileScript(source)).toEqual({ code: source, errors: [] });
	});

	it("reaches the parse for a key with a comment before its colon", () => {
		const errors = errorsOf(component('template /* c */ : "<p>{{ nope }}</p>",'));
		expect(errors).toMatchObject([{ line: 2, column: 27 }]);
	});

	it("leaves a destructured template alone", () => {
		const source = "const { template: text } = options\n";
		expect(compileScript(source)).toEqual({ code: source, errors: [] });
	});

	it("compiles a string and a backtick string", () => {
		const source = component('a: { template: "<p>a</p>" },\nb: { template: `<p>b</p>` },');
		const { code, errors } = compileScript(source);
		expect(errors).toEqual([]);
		expect(code).not.toContain("template:");
		expect(code.match(/render\(_ctx, _cache\)/g)).toHaveLength(2);
	});
});

describe("the literal-string rule", () => {
	it.each([
		["a variable", "  template: markup,", 13],
		["a ${} part", "  template: `<p>${name}</p>`,", 13],
		["the shorthand", "  template,", 3],
	])("refuses %s at the author's line", (_, line, column) => {
		const errors = errorsOf(`const markup = ""\nconst Card = {\n${line}\n}\n`);
		expect(errors).toEqual([
			{
				line: 3,
				column,
				message: "template: must be a string, or a backtick string with no ${} parts.",
			},
		]);
	});
});

describe("the names check", () => {
	it("accepts every name the component lists", () => {
		const source = `import { Badge } from "frappe-ui"
const Card = {
	name: "DealCard",
	components: { Badge, "my-panel": Badge },
	props: ["page"],
	inject: { theme: "theme" },
	setup() { const count = 1; return { count } },
	data: () => ({ open: false }),
	computed: { total() { return 1 } },
	methods: { save() {} },
	template: \`<div @click="save">
		<Badge :label="__('{0} items', [count])" />
		<badge :theme="theme" />
		<my-panel v-if="open" />
		<DealCard v-for="row in page.rows" :key="row.name" :row="row" />
		<RouterLink to="/"><span>{{ total }} {{ $route.path }} {{ Math.max(1, 2) }}</span></RouterLink>
		<Transition><p v-show="open">{{ __n('one', 'many', total) }}</p></Transition>
		<component :is="'Badge'" />
	</div>\`,
}`;
		expect(compileScript(source).errors).toEqual([]);
	});

	it("reports an unknown component and an unknown value with line and column", () => {
		const source = component("\ttemplate: `<div>\n\t\t<Badge :label=\"label\" />\n\t</div>`,");
		expect(errorsOf(source)).toEqual([
			{
				line: 3,
				column: 4,
				message: "<Badge> is not a known component. Import it and list it in components:.",
			},
			{
				line: 3,
				column: 18,
				message:
					'"label" is not a known name. Add it to props, setup(), data(), computed:, methods: or inject:.',
			},
		]);
	});

	it.each([
		["a bare handler", '<p @click="sav">a</p>', 12],
		["a handler with modifiers", '<p @keyup.enter.stop="sav">a</p>', 23],
		["a dynamic argument, at its bracket", '<p :[sav]="1">a</p>', 5],
	])("reports an unknown name in %s", (_, template, column) => {
		const source = component(`methods: { save() {} },\ntemplate: '${template}',`);
		expect(errorsOf(source)).toMatchObject([{ line: 3, column: 11 + column }]);
	});

	it("lets a setup() return named __ stand beside the global", () => {
		const source = component("setup() { return { __: (text) => text } },\ntemplate: \"<p>{{ __('a') }}</p>\",");
		expect(compileScript(source).errors).toEqual([]);
	});

	it.each([
		["components: as a variable", "components: shared,"],
		["a spread in the component", "...base,"],
		["a spread in a value list", "methods: { ...helpers },"],
		["a setup() that returns a variable", "setup() { return state },"],
		["a mixin", "mixins: [base],"],
	])("does not check a component with %s", (_, line) => {
		const source = component(`${line}\ntemplate: "<Unknown :a='missing' />",`);
		expect(compileScript(source).errors).toEqual([]);
	});
});

describe("line numbers", () => {
	const source = [
		'import { ref } from "vue"',
		"const count = ref(0)",
		"const Counter = {",
		"\tsetup: () => ({ count }),",
		"\ttemplate: `",
		"\t\t<ul>",
		'\t\t\t<li v-for="n in count" :key="n">{{ n }}</li>',
		"\t\t</ul>",
		'\t\t<p v-if="count > 2">many</p>',
		"\t`,",
		"}",
		'export const marker = new Error("line 12")',
		"export default Counter",
		"",
	].join("\n");

	it("keeps every line where it was, with the Vue import at the start of line 1", () => {
		const { code } = compileScript(source);
		const lines = code.split("\n");
		expect(lines).toHaveLength(source.split("\n").length);
		expect(lines[0]).toMatch(/^import \{ .* \} from "vue"; import \{ ref \} from "vue"$/);
		expect(lines[4]).toMatch(/^\trender\(_ctx, _cache\) \{.*\}?$/);
		expect(lines[9]).toBe("},");
		expect(lines.slice(11)).toEqual(source.split("\n").slice(11));
	});

	it("gives output that renders", async () => {
		const html = await render(source.replace("ref(0)", "ref(3)"));
		expect(html).toBe("<!--[--><ul><!--[--><li>1</li><li>2</li><li>3</li><!--]--></ul><p>many</p><!--]-->");
	});

	it("joins a line continuation inside an expression's string", async () => {
		const continued = "'a" + "\\\\" + "\n" + "b'";
		const source = component(`template: \`<p>{{ ${continued} }}</p>\`,`);
		expect(await render(source)).toBe("<p>ab</p>");
	});

	it("keeps a line break inside an expression's string on one line", async () => {
		const source = component('template: "<p>{{ `a\\nb`.length }}</p>",\nmarker: 1,');
		const { code } = compileScript(source);
		expect(code.split("\n")).toHaveLength(source.split("\n").length);
		expect(await render(source)).toBe("<p>3</p>");
	});
});

describe("the Vue import", () => {
	it("is left out when a template needs no helper", () => {
		const source = component('template: "hi",');
		expect(compileScript(source).code).not.toContain("import");
	});

	it("refuses a top-level name that a helper import also takes", () => {
		const source = `import { toDisplayString as _toDisplayString } from "vue"\n${component('template: "<p>{{ 1 }}</p>",')}`;
		expect(errorsOf(source)).toEqual([
			{
				line: 1,
				column: 29,
				message: '"_toDisplayString" is a name the compiled template needs. Rename it.',
			},
		]);
	});

	it("allows the same name inside a function", () => {
		const source = `function f(_toDisplayString) {}\n${component('template: "<p>{{ 1 }}</p>",')}`;
		expect(compileScript(source).errors).toEqual([]);
	});
});

describe("error positions", () => {
	it("adds the compiler's position to the template's start", () => {
		const source = component("\tname: 'x',\n\ttemplate: `\n\t\t<p>\n\t\t\t{{ a + }}\n\t\t</p>`,");
		const [error] = errorsOf(source);
		expect(error).toMatchObject({ line: 5, column: 7 });
		expect(error.message).toMatch(/expression/i);
	});

	it("counts escapes in a quoted string by their raw text", () => {
		const source = component('\ttemplate: "<p title=\\"a\\">\\n<Missing /></p>",');
		expect(errorsOf(source)).toMatchObject([{ line: 2, column: 31 }]);
	});

	it("reports a parse error at its place", () => {
		expect(errorsOf("const a = {\n  template: '<p></p>'\n  b: 1\n}\n")).toMatchObject([
			{ line: 3, column: 3 },
		]);
	});
});

describe("no author code runs", () => {
	const rows = "<p>static</p>".repeat(20);
	const template = `<div>${rows}<p>{{ this["process"]["pid"] }}</p></div>`;
	const pid = new RegExp(`\\b${process.pid}\\b`);

	it("would put the process id in the output with hoistStatic: true", () => {
		const { code } = compileTemplate({
			source: template,
			filename: "t",
			id: "t",
			compilerOptions: { hoistStatic: true },
		});
		expect(code).toMatch(pid);
	});

	it("keeps it out with the module's options", () => {
		const { code, errors } = compileScript(component(`template: '${template}',`));
		expect(errors).toEqual([]);
		expect(code).not.toMatch(pid);
	});
});

describe("the server entry", () => {
	const cli = path.join(folder, "../cli.mjs");
	const run = (input: string, ...args: string[]) =>
		JSON.parse(
			execFileSync("node", ["--disallow-code-generation-from-strings", cli, ...args], {
				input,
			}).toString()
		);

	it("compiles a list of scripts from stdin", () => {
		const results = run(
			JSON.stringify([
				{ name: "good", script: component('template: "<p>a</p>",') },
				{ name: "bad", script: component("template: markup,") },
			])
		);
		expect(results.map((result) => [result.name, result.errors.length])).toEqual([
			["good", 0],
			["bad", 1],
		]);
		expect(results[0].code).toContain("render(_ctx, _cache)");
		expect(results[1].code).toBeNull();
	});

	it("prints the cache key parts", () => {
		const parts = run("", "--key-parts");
		expect(parts).toEqual(cacheKeyParts());
		expect(parts.version).toBe(JSON.parse(fs.readFileSync(path.join(folder, "../../node_modules/vue/package.json"), "utf8")).version);
		expect(parts.options.compilerOptions.hoistStatic).toBe(false);
	});
});
