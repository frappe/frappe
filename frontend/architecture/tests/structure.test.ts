// @vitest-environment node
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { StructureCheck } from "../structure.mjs";

const doc = [
	"### 1. Lib",
	"",
	"| Concept | What it is |",
	"| --- | --- |",
	"| Data calls (`getDoc`, `Doc`) | Read a record |",
	"| `Button` | A button |",
	"",
	"### 2. App",
	"",
	"| Concept | What it is |",
	"| --- | --- |",
	"| `startApp` | Starts the app |",
	"",
].join("\n");

const files = {
	"ARCH.md": doc,
	"ui/package.json": JSON.stringify({ exports: { ".": "./src/index.ts" } }),
	"ui/src/index.ts": [
		'export * from "./api";',
		'export { default as Button } from "./components/Button.vue";',
		'export { helper as publicHelper } from "./utils/helper";',
	].join("\n"),
	"ui/src/api/index.ts": "export function getDoc() {}\nexport type Doc = { name: string };\nexport const hidden = 1;\n",
	"ui/src/components/Button.vue": "<template><button /></template>\n",
	"ui/src/utils/helper.ts": "export function helper() {}\n",
	"frontend/src/main.ts": [
		'import { getDoc, type Doc, Button } from "@framework/ui";',
		'import { startApp } from "./app/start";',
		'import type { Shape } from "./app/shape";',
		'const page = () => import("./pages/Page.vue");',
	].join("\n"),
	"frontend/src/app/start.ts": 'import { local } from "./local";\nexport function startApp() {}\n',
	"frontend/src/app/local.ts": "export const local = 1;\n",
	"frontend/src/app/shape.ts": "export type Shape = {};\n",
	"frontend/src/pages/Page.vue": "<template><div /></template>\n",
};

const unlisted = {
	"frontend/src/app/shape.ts": ["Shape"],
	"ui/src/api/index.ts": ["hidden"],
	"ui/src/utils/helper.ts": ["helper"],
};

function layerFile(knownUnlisted: Record<string, string[]>) {
	return {
		architecture: "ARCH.md",
		notUse: {},
		layers: [
			{ id: "2", section: "2-app", paths: ["frontend/src/"], mayUse: ["1"] },
			{ id: "1", section: "1-lib", paths: ["ui/src/"], mayUse: [] },
		],
		knownBreaks: [],
		knownLoops: [],
		knownUnlisted,
		flowEntries: [{ flow: "Boot", entry: "frontend/src/main.ts" }],
	};
}

let root: string;

function check(knownUnlisted: Record<string, string[]>) {
	const file = path.join(root, "frontend/architecture/layers.json");
	fs.writeFileSync(file, JSON.stringify(layerFile(knownUnlisted)));
	return new StructureCheck(root);
}

beforeAll(() => {
	root = fs.mkdtempSync(path.join(os.tmpdir(), "desk-structure-"));
	for (const [file, text] of Object.entries({ ...files, "frontend/architecture/layers.json": "" })) {
		fs.mkdirSync(path.dirname(path.join(root, file)), { recursive: true });
		fs.writeFileSync(path.join(root, file), text);
	}
	execFileSync("git", ["init", "-q"], { cwd: root });
});

afterAll(() => fs.rmSync(root, { recursive: true, force: true }));

describe("ConceptCheck", () => {
	it("fails on each name that crosses a folder and is in no concept table", () => {
		expect(check({}).report()).toEqual([
			"NO CONCEPT Shape (frontend/src/app/shape.ts): add it to layer 2's concept table",
			"NO CONCEPT hidden (ui/src/api/index.ts): add it to layer 1's concept table",
			"NO CONCEPT helper (ui/src/utils/helper.ts): add it to layer 1's concept table",
		]);
	});

	it("passes when every unlisted name is in the baseline", () => {
		const structure = check(unlisted);
		expect(structure.report()).toEqual([]);
		expect(structure.passes).toBe(true);
	});

	it("fails on a baseline name that no longer needs to be there", () => {
		const structure = check({ ...unlisted, "frontend/src/app/start.ts": ["startApp"] });
		expect(structure.report()).toEqual(["LISTED     startApp (frontend/src/app/start.ts): remove it from knownUnlisted"]);
	});
});

describe("FlowReach", () => {
	it("follows static and type imports, not dynamic ones", () => {
		const [boot] = check(unlisted).flows.flows;
		expect(boot.reached).toEqual([
			"frontend/src/app/local.ts",
			"frontend/src/app/shape.ts",
			"frontend/src/app/start.ts",
			"frontend/src/main.ts",
			"ui/src/api/index.ts",
			"ui/src/components/Button.vue",
			"ui/src/index.ts",
			"ui/src/utils/helper.ts",
		]);
	});
});
