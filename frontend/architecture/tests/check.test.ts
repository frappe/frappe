import { describe, expect, it } from "vitest";
import { LayerCheck } from "../check.mjs";
import { conceptsOf, flowsOf } from "../architectureDoc.mjs";

const layerFile = {
	notUse: { hook: "a callback" },
	layers: [
		{ id: "2", paths: ["app/pages/"], mayUse: ["1"] },
		{ id: "1", paths: ["app/", "app/lib/"], mayUse: [] },
	],
	knownBreaks: [{ from: "app/lib/old.ts", to: "app/pages/", ticket: 1, title: "Old break" }],
};

function node(id, ...files) {
	return { id, fileList: files.map((path) => ({ path, lines: 10 })), externals: {} };
}

function edge(from, to, kind, ...pairs) {
	return { from, to, kind, pairs };
}

function check(edges, nodes = [node("app/pages", "app/pages/Home.vue"), node("app/lib", "app/lib/new.ts", "app/lib/old.ts")]) {
	const read = () => 'import x from "./Home.vue";';
	return new LayerCheck({ nodes, edges, folderCycles: [] }, layerFile, read);
}

describe("LayerCheck", () => {
	it("places a file in the layer of its longest matching path", () => {
		const c = check([]);
		expect(c.layerOf("app/pages/Home.vue")).toBe("2");
		expect(c.layerOf("app/lib/new.ts")).toBe("1");
		expect(c.layerOf("other/x.ts")).toBeUndefined();
	});

	it("allows a use the layer file lists", () => {
		const c = check([
			edge("app/pages", "app/lib", "import", ["app/pages/Home.vue", "app/lib/new.ts"]),
			edge("app/lib", "app/lib", "import", ["app/lib/new.ts", "app/lib/old.ts"]),
		]);
		expect(c.edges.map((e) => e.status)).toEqual(["allowed", "inside"]);
		expect(c.passes).toBe(false);
		expect(c.fixedBreaks.map((k) => k.ticket)).toEqual([1]);
	});

	it("fails on a new break and names the import line", () => {
		const c = check([
			edge("app/lib", "app/pages", "import", ["app/lib/new.ts", "app/pages/Home.vue"], ["app/lib/old.ts", "app/pages/Home.vue"]),
		]);
		expect(c.edges[0].status).toBe("break");
		expect(c.newBreaks).toEqual([{ from: "app/lib/new.ts", to: "app/pages/Home.vue", line: 1, known: null }]);
		expect(c.report()).toEqual(["NEW BREAK  app/lib/new.ts:1 -> app/pages/Home.vue"]);
	});

	it("passes when every break is known", () => {
		const c = check([edge("app/lib", "app/pages", "import", ["app/lib/old.ts", "app/pages/Home.vue"])]);
		expect(c.edges[0].status).toBe("known");
		expect(c.passes).toBe(true);
	});

	it("does not count a callback as a use", () => {
		const c = check([
			edge("app/lib", "app/pages", "hook", ["app/lib/new.ts", "app/pages/Home.vue"]),
			edge("app/lib", "app/pages", "import", ["app/lib/old.ts", "app/pages/Home.vue"]),
		]);
		expect(c.edges[0].status).toBe("callback");
		expect(c.passes).toBe(true);
	});

	it("fails on a file in no layer", () => {
		const c = check([], [node("other", "other/x.ts")]);
		expect(c.unplaced).toEqual(["other/x.ts"]);
		expect(c.passes).toBe(false);
	});
});

const doc = `
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

## Where the code is not there yet
`;

describe("ARCHITECTURE.md reader", () => {
	it("reads a layer's concept table", () => {
		expect(conceptsOf(doc, { section: "6-shell" })).toEqual([{ name: "`AppShell`", what: "The root component" }]);
	});

	it("reads each flow's steps, layers and budget", () => {
		const [save] = flowsOf(doc);
		expect(save.title).toBe("Save: edit a field and save");
		expect(save.steps.map((s) => s.layers)).toEqual([["4"], ["main", "1"]]);
		expect(save.steps[1].check).toBe("Write permission");
		expect(save.budget).toBe("time until the saved state shows; request count.");
	});
});
