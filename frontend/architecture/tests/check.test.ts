import { describe, expect, it } from "vitest";
import { LayerCheck } from "../check.mjs";
import { conceptsOf, extensionsOf, flowsOf } from "../architectureDoc.mjs";

const layerFile = {
	notUse: { hook: "a callback" },
	layers: [
		{ id: "2", paths: ["app/pages/", "app/lib/page.ts"], mayUse: ["1"] },
		{ id: "1", paths: ["app/"], mayUse: [] },
	],
	knownBreaks: [{ from: "app/lib/old.ts", to: "app/pages/", ticket: 1, title: "Old break" }],
};

const nodes = [
	{ id: "app/pages", fileList: [{ path: "app/pages/Home.vue", lines: 10 }], externals: {} },
	{
		id: "app/lib",
		fileList: ["new.ts", "old.ts", "page.ts"].map((f) => ({ path: `app/lib/${f}`, lines: 10 })),
		externals: {},
	},
];

function edge(from, to, kind, ...pairs) {
	return { from, to, kind, pairs };
}

function check(edges, graphNodes = nodes) {
	return new LayerCheck({ nodes: graphNodes, edges, folderCycles: [] }, layerFile);
}

describe("LayerCheck", () => {
	it("places a file in the layer of its longest matching path", () => {
		const c = check([]);
		expect(c.layerOf("app/pages/Home.vue")).toBe("2");
		expect(c.layerOf("app/lib/new.ts")).toBe("1");
		expect(c.layerOf("app/lib/page.ts")).toBe("2");
		expect(c.layerOf("other/x.ts")).toBeUndefined();
	});

	it("allows a use the layer file lists, and skips a use inside one box", () => {
		const c = check([
			edge("app/pages", "app/lib", "import", ["app/pages/Home.vue", "app/lib/new.ts", 3]),
			edge("app/lib", "app/lib", "import", ["app/lib/new.ts", "app/lib/old.ts", 1]),
		]);
		expect(c.edges.map((e) => e.status)).toEqual(["allowed"]);
	});

	it("checks an import between two layers of one folder", () => {
		const c = check([edge("app/lib", "app/lib", "import", ["app/lib/new.ts", "app/lib/page.ts", 2])]);
		expect(c.edges[0]).toMatchObject({ from: "app/lib@1", to: "app/lib@2", status: "break" });
	});

	it("fails on a new break and names its line", () => {
		const c = check([
			edge(
				"app/lib",
				"app/pages",
				"import",
				["app/lib/new.ts", "app/pages/Home.vue", 7],
				["app/lib/old.ts", "app/pages/Home.vue", 1]
			),
		]);
		expect(c.edges[0].status).toBe("break");
		expect(c.newBreaks).toEqual([{ from: "app/lib/new.ts", to: "app/pages/Home.vue", line: 7, known: null }]);
		expect(c.report()).toEqual(["NEW BREAK  app/lib/new.ts:7 -> app/pages/Home.vue"]);
	});

	it("matches a known break by the exact file, not by a longer name", () => {
		const c = check(
			[edge("app/lib", "app/pages", "import", ["app/lib/old.tsx", "app/pages/Home.vue", 1])],
			[nodes[0], { id: "app/lib", fileList: [{ path: "app/lib/old.tsx", lines: 1 }], externals: {} }]
		);
		expect(c.newBreaks).toHaveLength(1);
	});

	it("passes when every break is known", () => {
		const c = check([edge("app/lib", "app/pages", "import", ["app/lib/old.ts", "app/pages/Home.vue", 1])]);
		expect(c.edges[0].status).toBe("known");
		expect(c.passes).toBe(true);
	});

	it("fails when a known break is gone, so the list only gets shorter", () => {
		const c = check([]);
		expect(c.fixedBreaks.map((k) => k.ticket)).toEqual([1]);
		expect(c.passes).toBe(false);
	});

	it("does not count a callback as a use", () => {
		const c = check([
			edge("app/lib", "app/pages", "hook", ["app/lib/new.ts", "app/pages/Home.vue", 1]),
			edge("app/lib", "app/pages", "import", ["app/lib/old.ts", "app/pages/Home.vue", 1]),
		]);
		expect(c.edges[0].status).toBe("callback");
		expect(c.passes).toBe(true);
	});

	it("fails on a file in no layer", () => {
		const c = check([edge("app/lib", "app/pages", "import", ["app/lib/old.ts", "app/pages/Home.vue", 1])], [
			...nodes,
			{ id: "other", fileList: [{ path: "other/x.ts", lines: 1 }], externals: {} },
		]);
		expect(c.unplaced).toEqual(["other/x.ts"]);
		expect(c.passes).toBe(false);
	});
});

const doc = `
### Outside the layers

**\`main.ts\`**

| Concept | What it is |
| --- | --- |
| Start sequence | Boot, then mount |

**The build**

| Concept | What it is |
| --- | --- |
| Manifest | The apps that add to the desk |

### 6. Shell

| Concept | What it is |
| --- | --- |
| \`AppShell\` | The root component |

## The five flows

### Save: edit a field and save

| # | Step | Layer | Permission check | Cache and key |
| --- | --- | --- | --- | --- |
| 1 | A field changes | 4 | None | None |
| 2 | The server saves | \`main.ts\`, 1 | Write permission | Data cache |

**Budget:** time until the saved state shows;
request count.

## Ways to change the desk

| Way | Who | Layer | How it is registered | What it changes | Same job as | Note |
| --- | --- | --- | --- | --- | --- | --- |
| record.js file script | App | 9 | A file | The record page | Stored script | |
| Stored script | Site | 9 | A Client Script row | The record page | record.js file script | |

## Where the code is not there yet
`;

describe("ARCHITECTURE.md reader", () => {
	it("reads a layer's concept table", () => {
		expect(conceptsOf(doc, { section: "6-shell" })).toEqual([{ name: "`AppShell`", what: "The root component" }]);
	});

	it("reads one of two tables under one heading", () => {
		const build = { section: "outside-the-layers", table: "**The build**" };
		expect(conceptsOf(doc, build)).toEqual([{ name: "Manifest", what: "The apps that add to the desk" }]);
	});

	it("reads the ways to change the desk", () => {
		expect(extensionsOf(doc).map((x) => [x.name, x.tier, x.pair])).toEqual([
			["record.js file script", "app", "Stored script"],
			["Stored script", "site", "record.js file script"],
		]);
	});

	it("reads each flow's steps, layers and budget", () => {
		const [save] = flowsOf(doc);
		expect(save.title).toBe("Save: edit a field and save");
		expect(save.steps.map((s) => s.layers)).toEqual([["4"], ["main", "1"]]);
		expect(save.steps[1].check).toBe("Write permission");
		expect(save.budget).toBe("time until the saved state shows; request count.");
	});
});
