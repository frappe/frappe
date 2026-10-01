// @vitest-environment node
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SourceMapConsumer } from "source-map-js";
import { build, createServer } from "vite";
import { afterAll, describe, expect, it } from "vitest";
import templateStrings from "../templateStrings.js";

const folder = path.dirname(fileURLToPath(import.meta.url));
// Outside node_modules, which the plugin skips; the real path, since vite reports that one.
const scratch = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "template-strings-")));

afterAll(() => fs.rmSync(scratch, { recursive: true, force: true }));

const COMPONENT = [
	"export default {",
	'  props: ["label"],',
	"  template: `",
	"    <p>{{ label }}</p>`,",
	"  mounted() {}",
	"};",
	"",
].join("\n");
const BROKEN = ["export default {", '  template: "<p>{{ label </p>",', "};", ""].join("\n");

function transform(source: string, id: string) {
	return (templateStrings() as any).transform.call(
		{
			error: (error: unknown) => {
				throw error;
			},
		},
		source,
		id
	);
}

function errorOf(source: string, id: string) {
	try {
		transform(source, id);
	} catch (error) {
		return error;
	}
	throw new Error("expected a template error");
}

function writeScratch(name: string, source: string) {
	const root = path.join(scratch, Math.random().toString(36).slice(2));
	fs.mkdirSync(path.dirname(path.join(root, name)), { recursive: true });
	fs.writeFileSync(path.join(root, name), source);
	return root;
}

describe("which files the plugin compiles", () => {
	it("compiles a .js and a .ts file outside node_modules", () => {
		expect(transform(COMPONENT, "/apps/crm/frontend/record.js").code).toContain("render(");
		expect(transform(COMPONENT, "/apps/crm/frontend/helper.ts").code).toContain("render(");
	});

	it("leaves a .vue file, a query id and a file with no template alone", () => {
		expect(transform(COMPONENT, "/apps/crm/Field.vue")).toBeNull();
		expect(transform(COMPONENT, "/apps/crm/Field.vue?vue&type=script&lang.ts")).toBeNull();
		expect(transform(COMPONENT, "/apps/crm/record.js?raw")).toBeNull();
		expect(transform("export default {};\n", "/apps/crm/record.js")).toBeNull();
	});

	it("skips a package in node_modules but compiles a package linked in from the bench", () => {
		const root = writeScratch("ui/src/Field.ts", COMPONENT);
		fs.mkdirSync(path.join(root, "node_modules/pkg"), { recursive: true });
		fs.writeFileSync(path.join(root, "node_modules/pkg/index.js"), COMPONENT);
		fs.mkdirSync(path.join(root, "node_modules/@framework"));
		fs.symlinkSync(path.join(root, "ui"), path.join(root, "node_modules/@framework/ui"));

		expect(transform(COMPONENT, path.join(root, "node_modules/pkg/index.js"))).toBeNull();
		const linked = path.join(root, "node_modules/@framework/ui/src/Field.ts");
		expect(transform(COMPONENT, linked).code).toContain("render(");
	});
});

describe("parity with the server entry", () => {
	it("gives the same code as cli.mjs for the same text", () => {
		const cli = path.join(folder, "../../templateCompiler/cli.mjs");
		const [server] = JSON.parse(
			execFileSync("node", [cli], {
				input: JSON.stringify([{ name: "record", script: COMPONENT }]),
			}).toString()
		);
		expect(transform(COMPONENT, "/apps/crm/frontend/record.js").code).toBe(server.code);
	});
});

describe("TypeScript files", () => {
	it("compiles a template beside type annotations, which stay for vite to strip", () => {
		const source = [
			"type Props = { label: string };",
			"export default {",
			'  props: ["label"],',
			'  template: "<p>{{ label }}</p>",',
			"  setup(props: Props) { return {}; },",
			"};",
			"",
		].join("\n");
		const { code } = transform(source, "/apps/crm/helper.ts");
		expect(code).toContain("render(");
		expect(code).toContain("setup(props: Props)");
	});

	it("reports an error at the author's line in a .ts file", () => {
		const source = ["type Props = { label: string };", "", BROKEN].join("\n");
		expect(errorOf(source, "/apps/crm/helper.ts")).toMatchObject({
			loc: { file: "/apps/crm/helper.ts", line: 4 },
		});
	});
});

describe("source maps", () => {
	it("maps the render function to its template key and later code to its own place", () => {
		const { code, map } = transform(COMPONENT, "/apps/crm/record.js");
		const consumer = new SourceMapConsumer(map);
		const lines = code.split("\n");
		const at = (needle: string) => {
			const line = lines.findIndex((text: string) => text.includes(needle)) + 1;
			return consumer.originalPositionFor({ line, column: lines[line - 1].indexOf(needle) });
		};
		expect(at("render(")).toMatchObject({ line: 3, column: 2 });
		expect(at("mounted")).toMatchObject({ line: 5, column: 2 });
		expect(at("export default")).toMatchObject({ line: 1, column: 0 });
	});
});

describe("template errors", () => {
	it("stop vite build with file, line, column and the compiler message", async () => {
		const root = writeScratch("record.js", BROKEN);
		const entry = path.join(root, "record.js");
		const failure = build({
			root,
			configFile: false,
			logLevel: "silent",
			plugins: [templateStrings()],
			build: { write: false, rollupOptions: { input: entry } },
		});
		await expect(failure).rejects.toThrow(/record\.js:2:\d+/);
		await expect(failure).rejects.toThrow(/Interpolation end sign was not found/);
	});

	it("reach the dev server's error screen with file, line and column", async () => {
		const root = writeScratch("record.js", BROKEN);
		const server = await createServer({
			root,
			configFile: false,
			logLevel: "silent",
			plugins: [templateStrings()],
			server: { middlewareMode: true, ws: false },
		});
		try {
			await expect(server.transformRequest("/record.js")).rejects.toMatchObject({
				loc: { file: path.join(root, "record.js"), line: 2 },
				message: expect.stringMatching(/Interpolation end sign was not found/),
			});
		} finally {
			await server.close();
		}
	});
});
