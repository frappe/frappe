import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { toast, runMethod } = vi.hoisted(() => ({
	toast: { error: vi.fn(), success: vi.fn() },
	runMethod: vi.fn(),
}));
vi.mock("frappe-ui", () => ({ toast }));
vi.mock("@framework/ui/api", () => ({ runMethod }));

import { acts } from "@/acts/dispatcher";
import { DANGER_METHOD, kindNotes, kindRefusal, type DangerHost } from "../dangerActs";
import type { EditorState } from "../editorSource";
import { mountEditor, taskNote } from "./editorFixture";

let stop: () => void;
beforeEach(() => {
	runMethod.mockReset();
	// Like the real runMethod: a 200 with no data throws unless the caller allows it.
	runMethod.mockImplementation(async (_method: string, _args: object, options?: { nullable?: boolean }) => {
		if (!options?.nullable) throw new Error("answered 200 with no data");
		return { data: null };
	});
	toast.success.mockReset();
});
afterEach(() => stop());

function mount(state: Partial<EditorState> = {}, danger: Partial<DangerHost> = {}) {
	const host: DangerHost = {
		scope: () => ({ developerMode: true, administrator: true }),
		settle: vi.fn(async () => true),
		askKind: vi.fn(async () => "submittable" as const),
		askName: vi.fn(async () => "Task Memo"),
		askModule: vi.fn(async () => "Core"),
		askDelete: vi.fn(async () => true as const),
		renamed: vi.fn(async () => undefined),
		deleted: vi.fn(async () => undefined),
		reload: vi.fn(async () => undefined),
		showing: vi.fn(() => true),
		...danger,
	};
	const loaded = taskNote(state);
	// Design's load carries the whole DocType, `custom` with it.
	loaded.definition = { ...loaded.definition, custom: loaded.custom };
	const mounted = mountEditor(loaded, { danger: host });
	stop = mounted.stop;
	return { host, mounted };
}

const offered = (name: string) => acts.available().some((act) => act.name === name);
const DANGER = ["change_kind", "rename_doctype", "move_doctype", "make_standard", "delete_doctype"];

describe("which Danger zone acts show", () => {
	it("offers all five on a saved custom DocType in Design, in developer mode", () => {
		mount();
		expect(DANGER.filter((name) => offered(`danger.${name}`))).toEqual(DANGER);
	});

	it("offers none in Customize, before the first save, or with a child table open", () => {
		mount({ mode: "Customize", modes: ["Customize"], custom: 0 });
		expect(DANGER.some((name) => offered(`danger.${name}`))).toBe(false);
		stop();
		mount({ pending: true });
		expect(DANGER.some((name) => offered(`danger.${name}`))).toBe(false);
		stop();
		mount({}, { scope: () => null });
		expect(DANGER.some((name) => offered(`danger.${name}`))).toBe(false);
	});

	it("leaves out Move and Make standard without developer mode", () => {
		mount({}, { scope: () => ({ developerMode: false, administrator: true }) });
		expect(DANGER.filter((name) => offered(`danger.${name}`))).toEqual(["change_kind", "rename_doctype", "delete_doctype"]);
	});
});

describe("running a Danger zone act", () => {
	it("holds every edit until the act and its reload finish", async () => {
		const seen: boolean[] = [];
		const { host, mounted } = mount({}, { reload: vi.fn(async () => void seen.push(mounted.edits.locked.value)) });
		runMethod.mockImplementationOnce(async () => {
			seen.push(mounted.edits.locked.value);
			return { data: null };
		});
		await acts.run("danger.change_kind");
		expect(host.reload).toHaveBeenCalled();
		expect(seen).toEqual([true, true]);
		expect(mounted.edits.locked.value).toBe(false);
	});

	it("changes the kind the dialog picks, then reloads", async () => {
		const { host } = mount();
		await acts.run("danger.change_kind");
		expect(host.askKind).toHaveBeenCalledWith(expect.objectContaining({ doctype: "Task Note" }));
		expect(runMethod).toHaveBeenCalledWith(DANGER_METHOD.change_kind, { doctype: "Task Note", kind: "submittable" }, { nullable: true });
		expect(toast.success).toHaveBeenCalled();
		expect(host.reload).toHaveBeenCalled();
	});

	it("takes the kind as its value without asking", async () => {
		const { host } = mount();
		await acts.run("danger.change_kind", { kind: "tree" });
		expect(host.askKind).not.toHaveBeenCalled();
		expect(runMethod).toHaveBeenCalledWith(DANGER_METHOD.change_kind, { doctype: "Task Note", kind: "tree" }, { nullable: true });
	});

	it("does nothing when the dialog is cancelled", async () => {
		const { host } = mount({}, { askKind: vi.fn(async () => null) });
		await acts.run("danger.change_kind");
		expect(runMethod).not.toHaveBeenCalled();
		expect(host.reload).not.toHaveBeenCalled();
	});

	it("renames, then follows the name the server answers", async () => {
		runMethod.mockResolvedValueOnce({ data: "Task Memo" });
		const { host } = mount();
		await acts.run("danger.rename_doctype");
		expect(runMethod).toHaveBeenCalledWith(DANGER_METHOD.rename_doctype, { doctype: "Task Note", new_name: "Task Memo" });
		expect(host.renamed).toHaveBeenCalledWith("Task Memo");
		expect(host.reload).not.toHaveBeenCalled();
	});

	it("moves to the module the dialog picks, and makes standard in one", async () => {
		const { host } = mount();
		await acts.run("danger.move_doctype");
		expect(host.askModule).toHaveBeenCalledWith(expect.objectContaining({ doctype: "Task Note" }), false);
		expect(runMethod).toHaveBeenCalledWith(DANGER_METHOD.move_doctype, { doctype: "Task Note", module: "Core" }, { nullable: true });
		await acts.run("danger.make_standard", { module: "Desk" });
		expect(runMethod).toHaveBeenCalledWith(DANGER_METHOD.make_standard, { doctype: "Task Note", module: "Desk" }, { nullable: true });
		expect(host.reload).toHaveBeenCalledTimes(2);
	});

	it("deletes once confirmed, then leaves for the DocType list", async () => {
		const { host } = mount();
		await acts.run("danger.delete_doctype");
		expect(host.askDelete).toHaveBeenCalledWith(expect.objectContaining({ doctype: "Task Note", record_count: 4 }));
		expect(runMethod).toHaveBeenCalledWith(DANGER_METHOD.delete_doctype, { doctype: "Task Note" }, { nullable: true });
		expect(host.deleted).toHaveBeenCalled();
	});

	it("skips the page's follow-up once the reader has left the DocType", async () => {
		const { host } = mount({}, { showing: vi.fn(() => false) });
		runMethod.mockResolvedValue({ data: "Task Memo" });
		for (const act of DANGER) await acts.run(`danger.${act}`);
		expect(runMethod).toHaveBeenCalledTimes(5);
		expect(host.showing).toHaveBeenCalledWith("Task Note");
		expect(host.reload).not.toHaveBeenCalled();
		expect(host.renamed).not.toHaveBeenCalled();
		expect(host.deleted).not.toHaveBeenCalled();
	});

	it("asks about pending edits first, and stops when they stay", async () => {
		const order: string[] = [];
		const { host, mounted } = mount(
			{},
			{
				settle: vi.fn(async () => (order.push("settle"), false)),
				askDelete: vi.fn(async () => (order.push("ask"), true as const)),
			},
		);
		await acts.run("danger.delete_doctype");
		expect(order).toEqual(["settle"]);
		expect(runMethod).not.toHaveBeenCalled();
		host.settle = vi.fn(async () => (order.push("settle"), true));
		await acts.run("danger.delete_doctype");
		expect(order).toEqual(["settle", "settle", "ask"]);
		expect(mounted.edits.canUndo.value).toBe(false);
	});
});

describe("the Change kind dialog's words", () => {
	it("refuses Single always, and Child table either way while records exist", () => {
		expect(kindRefusal("Contact", "regular", "single", 0)).toBe("Set when a DocType is made. Make a new Single instead.");
		expect(kindRefusal("Contact", "regular", "child", 125)).toBe(
			"Not while Contact has 125 records: a child table's rows need a parent record.",
		);
		expect(kindRefusal("Contact Phone", "child", "regular", 1)).toBe("Not while Contact Phone has 1 row: its rows belong to parent records.");
		expect(kindRefusal("Contact", "regular", "child", 0)).toBe("");
		expect(kindRefusal("Contact", "regular", "child", null)).toBe("");
		expect(kindRefusal("Contact", "regular", "regular", 125)).toBe("");
	});

	it("says what the pick changes", () => {
		expect(kindNotes("Contact", "regular", "submittable")).toEqual([
			"Adds an Amended From field. Submit, Cancel and Amend join the permissions grid.",
		]);
		expect(kindNotes("Contact", "submittable", "tree")).toEqual([
			"Records already submitted stay submitted.",
			"Adds 5 fields: lft, rgt, Is Group, Old Parent and Parent Contact.",
		]);
		expect(kindNotes("Contact", "tree", "regular")).toEqual(["The tree fields stay. Remove them in the Editor."]);
		expect(kindNotes("Contact", "regular", "regular")).toEqual([]);
	});
});
