// An agent's call never skips the confirm of `fields.delete_field` and `layouts.reset_to_app`;
// a person's script, whose panel or menu asks first, still does.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { dialog } = vi.hoisted(() => ({ dialog: { open: vi.fn(), confirm: vi.fn(), danger: vi.fn() } }));
vi.mock("@/shell/dialog", () => ({ shellDialog: () => dialog }));
vi.mock("frappe-ui", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { acts } from "@/acts/dispatcher";
import { mountEditor, taskNote } from "./editorFixture";
import { leadNote } from "./layoutsFixture";

let stop: () => void;
beforeEach(() => {
	dialog.open.mockReset();
	dialog.danger.mockReset();
});
afterEach(() => stop());

function mount(state: ReturnType<typeof taskNote>) {
	const mounted = mountEditor(state);
	stop = mounted.stop;
	return mounted;
}

describe("fields.delete_field", () => {
	it("a person's script removes the field with no question", async () => {
		const { canvas } = mount(taskNote());
		await acts.run("fields.delete_field", { fieldname: "status" });
		expect(dialog.danger).not.toHaveBeenCalled();
		expect(canvas.field("status")).toBeUndefined();
	});

	it("an agent's call asks first, and removes the field once a person says yes", async () => {
		dialog.danger.mockResolvedValueOnce(true);
		const { canvas } = mount(taskNote());
		expect(await acts.call("fields.delete_field", { fieldname: "status" }, { agent: true })).toMatchObject({ ok: true });
		expect(dialog.danger).toHaveBeenCalledWith(expect.objectContaining({ title: "Remove Status?" }));
		expect(canvas.field("status")).toBeUndefined();
	});

	it("an agent's call ends declined, and the field stays, when the person says no", async () => {
		dialog.danger.mockResolvedValueOnce(null);
		const { canvas, edits } = mount(taskNote());
		expect(await acts.call("fields.delete_field", { fieldname: "status" }, { agent: true })).toMatchObject({ ok: false, error: { code: "declined" } });
		expect([canvas.field("status")?.fieldname, edits.steps.length]).toEqual(["status", 0]);
	});

	it("an agent's call fails, and removes nothing, when the editor changed during the question", async () => {
		const { canvas, save } = mount(taskNote());
		dialog.danger.mockImplementationOnce(async () => {
			await save.reloadAndReapply();
			return true;
		});
		expect(await acts.call("fields.delete_field", { fieldname: "status" }, { agent: true })).toMatchObject({ ok: false, error: { code: "failed" } });
		expect(canvas.field("status")).toBeDefined();
	});

	it("an agent's call asks nothing for a field added since the save", async () => {
		const { canvas } = mount(taskNote());
		await acts.run("fields.add_field", { fieldname: "extra", fieldtype: "Data", label: "Extra" });
		expect(await acts.call("fields.delete_field", { fieldname: "extra" }, { agent: true })).toMatchObject({ ok: true });
		expect(dialog.danger).not.toHaveBeenCalled();
		expect(canvas.field("extra")).toBeUndefined();
	});
});

describe("layouts.reset_to_app", () => {
	const customize = () => leadNote({ mode: "Customize" });
	const staged = (edits: { staged: { value: unknown[] } }) => edits.staged.value;

	it("a person's script stages the reset with no dialog", async () => {
		const { edits } = mount(customize());
		await acts.run("layouts.reset_to_app", { type: "Details" });
		expect(dialog.open).not.toHaveBeenCalled();
		expect(staged(edits)).toEqual([{ act: "layouts.reset_to_app", type: "Details" }]);
	});

	it("an agent's call opens the dialog, and stages once a person confirms", async () => {
		dialog.open.mockResolvedValueOnce(true);
		const { edits } = mount(customize());
		expect(await acts.call("layouts.reset_to_app", { type: "Details" }, { agent: true })).toMatchObject({ ok: true });
		expect(dialog.open).toHaveBeenCalledTimes(1);
		expect(staged(edits)).toEqual([{ act: "layouts.reset_to_app", type: "Details" }]);
	});

	it("an agent's call fails, and stages nothing, when the editor changed during the dialog", async () => {
		const { edits, save } = mount(customize());
		dialog.open.mockImplementationOnce(async () => {
			await save.reloadAndReapply();
			return true;
		});
		expect(await acts.call("layouts.reset_to_app", { type: "Details" }, { agent: true })).toMatchObject({ ok: false, error: { code: "failed" } });
		expect(staged(edits)).toEqual([]);
	});

	it("an agent's call ends declined, and stages nothing, when the person cancels", async () => {
		dialog.open.mockResolvedValueOnce(null);
		const { edits } = mount(customize());
		expect(await acts.call("layouts.reset_to_app", { type: "Details" }, { agent: true })).toMatchObject({ ok: false, error: { code: "declined" } });
		expect(staged(edits)).toEqual([]);
	});
});
