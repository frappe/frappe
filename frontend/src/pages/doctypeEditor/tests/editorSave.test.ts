import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { toast, runMethod } = vi.hoisted(() => ({
	toast: { error: vi.fn(), success: vi.fn() },
	runMethod: vi.fn(),
}));
vi.mock("frappe-ui", () => ({ toast }));
vi.mock("@framework/ui/api", () => ({ runMethod }));

import { acts } from "@/acts/dispatcher";
import { CREATE_METHOD, SAVE_METHOD, WRITE_FILES_METHOD } from "../editorSave";
import type { EditorState } from "../editorSource";
import { ref } from "vue";
import { SettingsView } from "../settingsView";
import { mountEditor, taskNote, VERSION } from "./editorFixture";

const NEXT = { doctype: "2026-11-13 11:00:00", layouts: {}, app_layouts: { Details: "abc" } };

let stop: () => void;
beforeEach(() => {
	runMethod.mockReset();
	toast.error.mockReset();
	toast.success.mockReset();
});
afterEach(() => stop());

function mount(initial: EditorState = taskNote(), options: Parameters<typeof mountEditor>[1] = {}) {
	const mounted = mountEditor(initial, options);
	stop = mounted.stop;
	return mounted;
}

function answers(...results: unknown[]) {
	for (const data of results) runMethod.mockResolvedValueOnce({ data });
}

describe("editor.save", () => {
	it("sends the staged edits flat with the base version, then opens the reloaded DocType", async () => {
		const mounted = mount(taskNote(), { reloaded: () => taskNote({ base_version: NEXT }) });
		const { canvas, edits } = mounted;
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 });
		answers({ saved: true, base_version: NEXT, children: [] });
		await acts.run("editor.save");
		expect(runMethod).toHaveBeenCalledWith(SAVE_METHOD, {
			doctype: "Task Note",
			mode: "Design",
			base_version: VERSION,
			edits: [{ act: "fields.set_field_property", fieldname: "subject", property: "bold", value: 1 }],
		});
		expect(mounted.canvas).not.toBe(canvas);
		expect([edits.dirty.value, edits.payload().base_version]).toEqual([false, NEXT]);
		expect(toast.success).toHaveBeenCalledWith("Saved");
	});

	it("drops the saved edits and takes the new base version when the reload after a save fails", async () => {
		const { edits } = mount(taskNote(), {
			reloaded: () => {
				throw new Error("offline");
			},
		});
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 });
		answers({ saved: true, base_version: NEXT, children: [] });
		await expect(acts.run("editor.save")).rejects.toThrow("offline");
		expect([edits.dirty.value, edits.payload().base_version]).toEqual([false, NEXT]);
	});

	it("stages, undoes and redoes nothing while the save runs", async () => {
		const { edits } = mount();
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 });
		let answer!: (value: unknown) => void;
		runMethod.mockReturnValueOnce(new Promise((resolve) => (answer = resolve)));
		const saving = acts.run("editor.save");
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "italic", value: 1 });
		edits.undo();
		expect([edits.staged.value.length, edits.canUndo.value]).toEqual([1, false]);
		answer({ data: { saved: false, errors: [{ target: { kind: "banner" }, message: "No" }] } });
		await saving;
		expect([edits.staged.value.length, edits.canUndo.value]).toEqual([1, true]);
	});

	it("is off with nothing to save, and on for a new DocType with no edits", () => {
		mount();
		expect(acts.available().map((act) => act.name)).not.toContain("editor.save");
		stop();
		mount(taskNote({ pending: true }));
		expect(acts.find("editor.save")?.key).toBe("Mod+S");
	});

	it("creates a new DocType from its definition and layout, then offers its list", async () => {
		const openList = vi.fn();
		const pending = taskNote({ pending: true, doctype: "Walk Item", base_version: { doctype: "", layouts: {}, app_layouts: {} } });
		const mounted = mount(pending, { openList });
		await acts.run("settings.set_doctype_property", { property: "description", value: "Items" });
		answers({ saved: true, base_version: NEXT, children: [], doctype: "Walk Item" });
		await acts.run("editor.save");
		expect(runMethod).toHaveBeenCalledWith(CREATE_METHOD, {
			definition: pending.definition,
			layout: pending.layouts.Details![0].layout,
			edits: [{ act: "settings.set_doctype_property", property: "description", value: "Items" }],
		});
		expect(mounted.created).toEqual(["Walk Item"]);
		expect(mounted.save.banner.value).toMatchObject({ title: "Walk Item is created.", offers: ["editor.open_list"] });
		await acts.run("editor.open_list");
		expect(openList).toHaveBeenCalled();
	});

	it("leaves the Settings tab on the reloaded DocType's settings", async () => {
		const reloaded = taskNote();
		reloaded.definition.title_field = "subject";
		const mounted = mount(taskNote(), { reloaded: () => reloaded });
		const view = new SettingsView(() => mounted.canvas, ref({ section: "", found: null }), () => null);
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 });
		answers({ saved: true, base_version: NEXT, children: [] });
		await acts.run("editor.save");
		expect(view.value("title_field")).toBe("subject");
	});

	it("marks a mandatory field off the layout as asked for on save", async () => {
		const mounted = mount();
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 });
		answers({ saved: true, base_version: NEXT, children: [] });
		await acts.run("editor.save");
		expect(mounted.canvas.offLayout.value.map((row) => [row.field.fieldname, row.asked])).toEqual([["spare", true]]);
	});
});

describe("a refused save", () => {
	it("shows field and section errors at their targets, and the rest in the banner", async () => {
		const { canvas, save } = mount();
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 });
		answers({
			saved: false,
			errors: [
				{ target: { kind: "field", fieldname: "notes", property: "options" }, message: "Notes needs options." },
				{ target: { kind: "container", container: "more" }, message: "More is empty." },
				{ target: { kind: "layout", layout: "x" }, message: "Only one Details layout can have no condition." },
			],
		});
		await acts.run("editor.save");
		expect(canvas.errorsAt("field", "notes")).toEqual(["Notes needs options."]);
		expect(canvas.errorsAt("container", "more")).toEqual(["More is empty."]);
		expect(canvas.selection.value).toEqual({ kind: "field", fieldname: "notes" });
		expect(save.banner.value).toMatchObject({
			title: "Not saved",
			messages: ["Only one Details layout can have no condition."],
			offers: [],
		});
	});

	it("opens the setting a save error marks", async () => {
		const mounted = mount();
		await acts.run("settings.set_doctype_property", { property: "title_field", value: "notes" });
		answers({ saved: false, errors: [{ target: { kind: "setting", property: "title_field" }, message: "Notes is not a title." }] });
		await acts.run("editor.save");
		expect([mounted.tab.value, mounted.foundSettings]).toEqual(["settings", ["title_field"]]);
		expect(mounted.canvas.errorsAt("setting", "title_field")).toEqual(["Notes is not a title."]);
	});

	it("when stale, reloads and re-applies the edits, and lists the ones refused", async () => {
		const changed = taskNote({ base_version: NEXT });
		changed.definition.fields = changed.definition.fields.filter((field) => field.fieldname !== "status");
		const { save, edits } = mount(taskNote(), { reloaded: () => changed });
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 });
		await acts.run("fields.set_field_property", { fieldname: "status", property: "bold", value: 1 });
		answers({
			saved: false,
			errors: [{ target: { kind: "banner" }, code: "stale", message: "Changed by Jo at 10:30 since you opened it." }],
		});
		await acts.run("editor.save");
		expect(save.banner.value?.offers).toEqual(["editor.reload_and_reapply"]);
		await acts.run("editor.reload_and_reapply");
		expect(edits.payload()).toMatchObject({
			base_version: NEXT,
			edits: [{ act: "fields.set_field_property", fieldname: "subject", property: "bold", value: 1 }],
		});
		expect(save.banner.value).toMatchObject({
			title: "1 edit could not be applied again",
			messages: ["status is not a field of Task Note."],
		});
	});

	it("holds Save and every edit until the reload re-applies them", async () => {
		const { save, edits } = mount(taskNote(), { reloaded: () => taskNote({ base_version: NEXT }) });
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 });
		const reapplying = save.reloadAndReapply();
		expect([save.saving.value, edits.locked.value]).toEqual([true, true]);
		await save.save();
		expect(runMethod).not.toHaveBeenCalled();
		await reapplying;
		expect([save.saving.value, edits.staged.value.length]).toEqual([false, 1]);
	});

	it("runs this DocType's export that lands during the save once the save's own reload is done", async () => {
		let reloads = 0;
		const { save } = mount(taskNote({ custom: 0 }), {
			reloaded: () => (reloads++, taskNote({ custom: 0, base_version: NEXT })),
		});
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 });
		let answer!: (value: unknown) => void;
		runMethod.mockReturnValueOnce(new Promise((resolve) => (answer = resolve)));
		const saving = acts.run("editor.save");
		await save.exported({ doctype: "Task Note", ok: true, app_layouts: { Details: "abc" } });
		await save.exported({ doctype: "Other", ok: false, error: "Disk full" });
		expect(reloads).toBe(0);
		answer({ data: { saved: true, base_version: NEXT, children: [] } });
		await saving;
		await vi.waitFor(() => expect(reloads).toBe(2));
	});
});

describe("a failed file export", () => {
	it("offers Write files again, which writes them and moves the base version", async () => {
		const { save, edits } = mount(taskNote({ custom: 0 }));
		await save.exported({ doctype: "Other", ok: false, error: "Disk full" });
		expect(save.banner.value).toBeNull();
		await save.exported({ doctype: "Task Note", ok: false, error: "Disk full" });
		expect(save.banner.value).toMatchObject({ messages: ["Disk full"], offers: ["editor.write_files_again"] });
		answers({ Details: "def" });
		await acts.run("editor.write_files_again");
		expect(runMethod).toHaveBeenCalledWith(WRITE_FILES_METHOD, { doctype: "Task Note" }, { nullable: true });
		expect([save.banner.value, edits.payload().base_version.app_layouts]).toEqual([null, { Details: "def" }]);
	});

	it("reloads after a successful export, or with edits staged takes its versions as the next base", async () => {
		const mounted = mount(taskNote({ custom: 0 }), { reloaded: () => taskNote({ custom: 0, base_version: NEXT }) });
		const before = mounted.canvas;
		await mounted.save.exported({ doctype: "Task Note", ok: true, app_layouts: { Details: "abc" } });
		expect([mounted.canvas === before, mounted.edits.payload().base_version]).toEqual([false, NEXT]);
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 });
		await mounted.save.exported({ doctype: "Task Note", ok: true, app_layouts: { Details: "def" } });
		expect(mounted.edits.payload().base_version).toEqual({ ...NEXT, app_layouts: { Details: "def" } });
		expect(mounted.edits.dirty.value).toBe(true);
	});
});
