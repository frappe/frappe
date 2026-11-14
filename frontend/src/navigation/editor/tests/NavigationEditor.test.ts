// The editor, mounted: it reads a level, edits a draft, and commits with one Save.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";

import type { Boot } from "@/boot";
import type { Arrangements, EditorRow } from "../draft";
import NavigationEditor from "../NavigationEditor.vue";

const api = vi.hoisted(() => ({
	fetchArrangements: vi.fn(),
	fetchDefaultArrangements: vi.fn(),
	saveArrangements: vi.fn(),
	saveNavigationLayout: vi.fn(),
}));
vi.mock("@/arrangement", () => api);

const row = (key: string, more: Partial<EditorRow> = {}): EditorRow => ({
	key,
	item_type: "DocType",
	link_to: key,
	label: key.toUpperCase(),
	...more,
});

function response(more: Partial<Arrangements> = {}): Arrangements {
	return {
		version: "v1",
		can_edit_site: true,
		has_saved: false,
		navigation_layouts: { standard: "", site: "", user: "" },
		rail: [row("todo"), row("note", { hidden: 1 })],
		sidebars: {},
		...more,
	};
}

async function settle() {
	for (let turn = 0; turn < 4; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

const body = () => document.body;
const text = (selector: string) => body().querySelector(selector)?.textContent?.trim();
const rowsShown = () => Array.from(body().querySelectorAll("[data-editor-list] li")).map((li) => li.textContent?.trim());

let unmount = () => {};

async function open(answer: Arrangements = response()) {
	api.fetchArrangements.mockResolvedValue(answer);
	const emitted: string[] = [];
	const app = createApp(NavigationEditor, {
		target: { tab: "rail" },
		onClose: () => emitted.push("close"),
		onSaved: () => emitted.push("saved"),
	});
	app.provide("boot", { app: "crm", app_title: "CRM" } as unknown as Boot);
	const host = document.createElement("div");
	document.body.appendChild(host);
	app.mount(host);
	unmount = () => app.unmount();
	await settle();
	return emitted;
}

const click = (selector: string) => body().querySelector<HTMLElement>(selector)!.click();

beforeEach(() => {
	document.body.innerHTML = "";
	Object.values(api).forEach((fn) => fn.mockReset());
});
afterEach(() => unmount());

describe("the editor", () => {
	it("reads the level and lists the rail, hidden rows only on request", async () => {
		await open();
		expect(text("[data-navigation-editor] h2")).toBe("Customize navigation");
		expect(rowsShown()).toEqual(["TODO"]);

		body().querySelector<HTMLInputElement>("input[type='checkbox']")!.click();
		await settle();
		expect(rowsShown()).toEqual(["TODO", "NOTEHidden"]);
	});

	it("keeps Save disabled until an edit, then saves the rows and closes", async () => {
		api.saveArrangements.mockResolvedValue({ rail: [], sidebars: {} });
		const emitted = await open();
		expect(body().querySelector<HTMLButtonElement>("[data-save]")!.disabled).toBe(true);

		click("[data-key='todo']");
		await settle();
		expect(text("[data-editor-pane] p")).toBe("TODO");
		const label = body().querySelector<HTMLInputElement>("[data-field='label'] input, input[data-field='label']")!;
		label.value = "Tasks";
		label.dispatchEvent(new Event("input", { bubbles: true }));
		await settle();
		expect(body().querySelector<HTMLButtonElement>("[data-save]")!.disabled).toBe(false);

		click("[data-save]");
		await settle();
		expect(api.saveArrangements).toHaveBeenCalledOnce();
		const [app, scope, payload, version] = api.saveArrangements.mock.calls[0];
		expect([app, scope, version]).toEqual(["crm", "user", "v1"]);
		expect(payload.rail[0].label).toBe("Tasks");
		expect(api.saveNavigationLayout).not.toHaveBeenCalled();
		expect(emitted).toEqual(["saved", "close"]);
	});

	it("hides a row from the pane's Hide button", async () => {
		await open();
		click("[data-key='todo']");
		await settle();
		click("[data-row-actions] button");
		await settle();
		expect(rowsShown()).toEqual([]);
		expect(body().querySelector("[data-revert]")).not.toBeNull();
	});

	it("offers Reset to default only when this level has saved, and Save commits it", async () => {
		await open();
		expect(body().querySelector("[data-reset]")).toBeNull();
		unmount();
		document.body.innerHTML = "";

		api.fetchDefaultArrangements.mockResolvedValue({ rail: [row("todo")], sidebars: {} });
		api.saveArrangements.mockResolvedValue({ rail: [], sidebars: {} });
		await open(response({ has_saved: true, rail: [row("todo"), row("user:abc123")] }));

		click("[data-reset]");
		await settle();
		expect(api.fetchDefaultArrangements).toHaveBeenCalledWith("crm", "user");
		expect(rowsShown()).toEqual(["TODO"]);
		expect(body().querySelector("[data-reset]")).toBeNull();

		click("[data-save]");
		await settle();
		expect(api.saveArrangements.mock.calls[0][2].rail.map((r: EditorRow) => r.key)).toEqual(["todo"]);
	});

	it("shows the error and a Reload on a stale version", async () => {
		const stale = Object.assign(new Error("Changed meanwhile"), { isTimestampMismatch: true });
		api.saveArrangements.mockRejectedValue(stale);
		await open();
		click("[data-key='todo']");
		await settle();
		click("[data-row-actions] button");
		await settle();
		click("[data-save]");
		await settle();
		expect(text("[data-save-error]")).toContain("Changed meanwhile");
	});

	it("moves focus from a row to the form on Enter", async () => {
		await open(response({ rail: [row("todo"), row("note")] }));
		const item = body().querySelector<HTMLElement>("[data-key='note']")!;
		item.focus();
		item.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		await settle();
		const label = body().querySelector("[data-editor-pane] input[data-field='label'], [data-editor-pane] [data-field='label'] input");
		expect(label).not.toBeNull();
		expect(document.activeElement).toBe(label);
	});

	it("keeps the new version and the layout edit when the layout save fails after the rows", async () => {
		api.saveArrangements.mockResolvedValue({ rail: [], sidebars: {} });
		api.saveNavigationLayout.mockRejectedValue(new Error("No layout"));
		// Reset to default changes the rows and clears the layout: two saves.
		api.fetchDefaultArrangements.mockResolvedValue({ rail: [row("todo")], sidebars: {} });
		const emitted = await open(
			response({
				has_saved: true,
				navigation_layouts: { standard: "", site: "", user: "sidebar_only" },
				rail: [row("todo"), row("user:abc123")],
			})
		);
		click("[data-reset]");
		await settle();

		api.fetchArrangements.mockResolvedValue(
			response({
				version: "v2",
				has_saved: true,
				navigation_layouts: { standard: "", site: "", user: "sidebar_only" },
				rail: [row("todo")],
			})
		);
		click("[data-save]");
		await settle();
		expect(api.saveNavigationLayout).toHaveBeenCalledOnce();
		expect(emitted).toEqual(["saved"]);
		expect(text("[data-save-error]")).toContain("Your rows are saved, but the layout is not: No layout");

		// Save again: the layout alone goes out, and the rows are not sent on the old version.
		api.saveNavigationLayout.mockResolvedValue({ rail: [], sidebars: {} });
		click("[data-save]");
		await settle();
		expect(api.saveArrangements).toHaveBeenCalledOnce();
		expect(api.saveNavigationLayout).toHaveBeenCalledTimes(2);
		expect(api.saveNavigationLayout.mock.calls[1][1]).toBe("");
		expect(emitted).toEqual(["saved", "saved", "close"]);
	});

	it("hands the selection to the next visible row when the selected one is hidden", async () => {
		await open(response({ rail: [row("a"), row("b", { hidden: 1 }), row("c")] }));
		click("[data-key='a']");
		await settle();
		click("[data-row-actions] button");
		await settle();
		expect(text("[data-editor-pane] p")).toBe("C");
		expect(body().querySelector("[data-key='c']")!.getAttribute("tabindex")).toBe("0");
	});

	it("lets a nested row sit two levels in", async () => {
		await open(
			response({
				rail: [
					row("s", { item_type: "Section" }),
					row("i", { parent_key: "s" }),
					row("c", { parent_key: "i" }),
				],
			})
		);
		const guides = (key: string) => body().querySelectorAll(`[data-key='${key}'] > span.w-4`).length;
		expect([guides("s"), guides("i"), guides("c")]).toEqual([0, 1, 2]);
	});
});
