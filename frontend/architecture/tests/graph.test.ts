// @vitest-environment node
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { buildGraph } from "../graph.mjs";

const files = {
	"ui/package.json": JSON.stringify({ exports: { ".": "./src/index.ts", "./api": "./src/api/index.ts" } }),
	"ui/src/index.ts": "export const x = 1;\n",
	"ui/src/api/index.ts": "export default {};\n",
	"frontend/plugin/contributions.js": "export default {};\n",
	"frontend/src/types.ts": "export type A = string;\n",
	"frontend/src/ignored.ts": "export {};\n",
	"frontend/src/main.ts": [
		"/* a comment that spans",
		'   two lines: import "./ignored" */',
		'import type { A } from "./types";',
		'import { x } from "@framework/ui";',
		'import api from "@framework/ui/api";',
		'import registry from "virtual:frappe/contributions";',
		'const home = () => import("@/pages/Home.vue");',
		'// import "./ignored";',
		'call("frappe.shell.boot.get_boot");',
	].join("\n"),
	"frontend/src/pages/Home.vue": '<script setup>\nimport Other from "./Other.vue";\nimport rows from "@/list/rows";\n</script>\n',
	"frontend/src/pages/Other.vue": "<template><div /></template>\n",
	"frontend/src/list/rows.ts": 'import Other from "@/pages/Other.vue";\nexport default Other;\n',
	"frappe/utils/__init__.py": "",
	"frappe/utils/data.py": "from frappe.shell.links import route\n",
	"frappe/hooks.py": 'page_renderer = ["frappe.shell.boot.Page"]\n',
	"frappe/shell/links.py": "def route():\n\tpass\n",
	"frappe/shell/boot.py": "from .links import route\nfrom frappe.utils import data\n",
};

let root: string;
let graph: ReturnType<typeof buildGraph>;

beforeAll(() => {
	root = fs.mkdtempSync(path.join(os.tmpdir(), "desk-graph-"));
	for (const [file, text] of Object.entries(files)) {
		fs.mkdirSync(path.dirname(path.join(root, file)), { recursive: true });
		fs.writeFileSync(path.join(root, file), text);
	}
	// The graph reads frappe.shell references through `git grep`, which sees tracked files only.
	execFileSync("git", ["init", "-q"], { cwd: root });
	execFileSync("git", ["add", "."], { cwd: root });
	graph = buildGraph(root);
});

afterAll(() => fs.rmSync(root, { recursive: true, force: true }));

function edge(from: string, to: string, kind = "import") {
	return graph.edges.find((e) => e.from === from && e.to === to && e.kind === kind);
}

describe("buildGraph", () => {
	it("reads each kind of JS import, with its line", () => {
		const main = "frontend/src/main.ts";
		expect(edge(main, "frontend/src/types.ts")).toMatchObject({ typeOnly: 1, pairs: [[main, "frontend/src/types.ts", 3]] });
		expect(edge(main, "ui/src/index.ts")?.pairs).toEqual([[main, "ui/src/index.ts", 4]]);
		expect(edge(main, "ui/src/api")?.pairs).toEqual([[main, "ui/src/api/index.ts", 5]]);
		expect(edge(main, "frontend/plugin", "virtual")?.pairs[0][2]).toBe(6);
		expect(edge(main, "frontend/src/pages")).toMatchObject({ dynamic: 1 });
		expect(edge(main, "frappe/shell/boot.py", "api")?.pairs[0][2]).toBe(9);
	});

	it("skips imports inside comments", () => {
		expect(edge("frontend/src/main.ts", "frontend/src/ignored.ts")).toBeUndefined();
	});

	it("keeps an import between two files of one folder", () => {
		expect(edge("frontend/src/pages", "frontend/src/pages")?.pairs).toEqual([
			["frontend/src/pages/Home.vue", "frontend/src/pages/Other.vue", 2],
		]);
	});

	it("reads relative and absolute Python imports, and hooks.py names", () => {
		expect(edge("frappe/shell/boot.py", "frappe/shell/links.py")?.pairs[0][2]).toBe(1);
		expect(edge("frappe/shell/boot.py", "frappe/utils")?.pairs[0][2]).toBe(2);
		expect(edge("frappe/utils", "frappe/shell/links.py")?.pairs[0][2]).toBe(1);
		expect(edge("frappe", "frappe/shell/boot.py", "hook")).toBeDefined();
	});

	it("finds folders that import each other", () => {
		expect(graph.folderCycles).toEqual([["frontend/src/list", "frontend/src/pages"]]);
	});
});
