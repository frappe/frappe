// `window.desk`: a frozen facade whose list, options and state read what the page holds now.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("frappe-ui", () => ({ dialog: { confirm: vi.fn(), danger: vi.fn() }, toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@framework/ui/api", () => ({ getTranslations: vi.fn() }));

import { acts, type ActScope } from "@/acts/dispatcher";
import { installDesk } from "../windowDesk/install";

const releases: Array<() => void> = [];

function register(surfaces: ActScope["surfaces"], rest: Partial<ActScope> = {}) {
	releases.push(
		acts.register({
			surfaces,
			context: () => null,
			passes: () => true,
			settled: () => undefined,
			hold: async (work: () => unknown) => work(),
			failed: () => {},
			...rest,
		} as unknown as ActScope)
	);
}

const item = (fields: Record<string, unknown>) => ({ item: { name: "go", run: () => 1, ...fields } as any, hidden: false });

// The binding is not configurable, so it is set once for the file.
beforeAll(() => installDesk());

afterEach(() => releases.splice(0).forEach((release) => release()));

describe("window.desk", () => {
	it("is frozen, version 1, and set once", () => {
		const desk = window.desk!;
		installDesk();

		expect(window.desk).toBe(desk);
		expect(desk.version).toBe(1);
		expect(Object.isFrozen(desk) && Object.isFrozen(desk.acts)).toBe(true);
		expect(() => ((window as any).desk = {})).toThrow(TypeError);
		expect(() => delete (window as any).desk).toThrow(TypeError);
	});

	it("lists every act that can run now with its description, schema and surface", async () => {
		register({
			plain: () => [
				item({ label: "Go", description: "Goes.", input: { type: "string" }, asks: ["confirm"], key: "Mod+G", palette: false }),
				{ ...item({ name: "gone" }), hidden: true },
			],
		});

		expect(await window.desk!.acts.list()).toEqual([
			{ name: "plain.go", label: "Go", description: "Goes.", input: { type: "string" }, asks: ["confirm"], surface: "plain", key: "Mod+G", has_options: false },
		]);
	});

	it("falls back to the label for a description, and to no input and no asks", async () => {
		register({ plain: () => [item({ label: "Go" })] });

		expect(await window.desk!.acts.list()).toMatchObject([{ description: "Go", input: null, asks: [] }]);
	});

	it("returns an act's options in run's envelope, and an error for an act with none", async () => {
		register({
			plain: () => [
				item({ argument: { label: "Who", options: (_: unknown, query: string) => [{ value: query, label: "Ann", icon: "x" }] } }),
				item({ name: "bare" }),
			],
		});

		expect(await window.desk!.acts.options("plain.go", "an")).toMatchObject({ ok: true, data: [{ value: "an", label: "Ann" }] });
		expect(await window.desk!.acts.options("plain.bare")).toMatchObject({ ok: false, error: { code: "failed" } });
		expect(await window.desk!.acts.options("plain.nope")).toMatchObject({ ok: false, error: { code: "missing" } });
	});

	it("reads a list page's doctype, filters, sort and selection", async () => {
		const router = { currentRoute: { value: { name: "list" } } };
		register({ shell: () => [] }, { context: () => ({ router }) });
		const facts = {
			doctype: "ToDo",
			filters: [["status", "=", "Open"]],
			sort: [{ fieldname: "modified", direction: "desc" }],
			selected: ["a", "b"],
			rows: [{ name: "a", title: "A" }],
		};
		register({ list: () => [] }, { facts: async () => facts });

		expect(await window.desk!.state()).toMatchObject({ page: "list", ...facts, dialogs: [] });
	});

	it("reads a record page's facts, and caps the fields it adds", async () => {
		const router = { currentRoute: { value: { name: "record" } } };
		const fields = Array.from({ length: 200 }, (_, index) => ({ fieldname: `f${index}`, value: "x".repeat(50) }));
		register({ shell: () => [] }, { context: () => ({ router }) });
		register(
			{ record: () => [] },
			{ facts: async (withFields: boolean) => ({ doctype: "ToDo", name: "T1", docstatus: 0, unsaved: true, ...(withFields && { fields }) }) }
		);

		expect(await window.desk!.state()).toMatchObject({ page: "record", doctype: "ToDo", name: "T1", unsaved: true });
		const full = (await window.desk!.state({ fields: true })) as any;
		expect(full.truncated).toBe(true);
		expect(JSON.stringify(full.fields).length).toBeLessThanOrEqual(6000);
	});

	it("says a record route is loading while its page has registered nothing, and names other routes", async () => {
		const at = (name: string) => register({ shell: () => [] }, { context: () => ({ router: { currentRoute: { value: { name } } } }) });
		at("record");
		expect(await window.desk!.state()).toMatchObject({ page: "record", loading: true });
		releases.splice(0).forEach((release) => release());

		for (const [name, page] of [["home", "home"], ["new-record", "new"], ["doctype-editor", "editor"], ["not-found", "not_found"], ["anything", "page"]]) {
			at(name);
			expect(await window.desk!.state()).toMatchObject({ page });
			releases.splice(0).forEach((release) => release());
		}
	});

	it("reads a record page's facts through a dialog's scope laid over it", async () => {
		const router = { currentRoute: { value: { name: "record" } } };
		register({ shell: () => [] }, { context: () => ({ router }) });
		register({ record: () => [] }, { facts: async () => ({ doctype: "ToDo", name: "T1", docstatus: 0, unsaved: false }) });
		register({ record: () => [] });

		expect(await window.desk!.state()).toMatchObject({ page: "record", doctype: "ToDo", name: "T1" });
	});
});
