// The list.js files come from a generated module only the list page imports, so no other page carries them.
import { globSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";

const { load } = vi.hoisted(() => ({ load: () => Promise.resolve({ default: {} }) }));

vi.mock("virtual:frappe/list-scripts", () => ({
	default: [
		{ kind: "customList", app: "crm", doctype: "HD Ticket", load },
		{ kind: "list", app: "helpdesk", doctype: "HD Ticket", load },
		{ kind: "customList", app: "telephony", doctype: "HD Ticket", load },
	],
}));
import { registerContributions } from "@/contributions/registry";
import { listScriptsFor } from "../listScriptFiles";

registerContributions(["frappe", "telephony", "helpdesk", "crm"]);

const root = join(dirname(fileURLToPath(import.meta.url)), "../../../..");

// The source files that import `spec`; a relative `./name` counts only beside the list page's loader.
function importersOf(spec: string): string[] {
	const name = spec.split("/").at(-1);
	return globSync(["frontend/src/**/*.{ts,vue}", "ui/src/**/*.{ts,vue}"], { cwd: root })
		.filter((file) => !file.includes("/tests/"))
		.filter((file) => {
			const source = readFileSync(join(root, file), "utf8");
			const local = dirname(file) === "frontend/src/listPage" && source.includes(`from "./${name}"`);
			return local || [`from "${spec}"`, `from '${spec}'`, `import("${spec}")`].some((form) => source.includes(form));
		})
		.sort();
}

describe("the list script files", () => {
	it("run the owning app's list.js first, then each custom one in the site's app order", () => {
		expect(listScriptsFor("HD Ticket").map((script) => script.app)).toEqual(["helpdesk", "telephony", "crm"]);
		expect(listScriptsFor("Contact")).toEqual([]);
	});

	it("are imported by the list page's loader alone, never the shell", () => {
		expect(importersOf("virtual:frappe/list-scripts")).toEqual([
			"frontend/src/listPage/listScriptFiles.ts",
		]);
		expect(importersOf("@/listPage/listScriptFiles")).toEqual([
			"frontend/src/listPage/scriptLoader.ts",
		]);
		expect(importersOf("@/listPage/scriptLoader")).toEqual([
			"frontend/src/listPage/createListPage.ts",
		]);
	});
});
