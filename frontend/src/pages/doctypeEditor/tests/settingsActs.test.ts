import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { toast } = vi.hoisted(() => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("frappe-ui", () => ({ toast }));

import { acts } from "@/acts/dispatcher";
import type { EditorState } from "../editorSource";
import { mountEditor, taskNote } from "./editorFixture";

let stop: () => void;
beforeEach(() => toast.error.mockReset());
afterEach(() => stop());

const NO_RIGHTS = { select: 0, read: 0, write: 0, create: 0, delete: 0, submit: 0, cancel: 0, amend: 0, print: 0, email: 0, report: 0, import: 0, export: 0, share: 0 };
const writer = { ...NO_RIGHTS, role: "Writer", permlevel: 0, if_owner: 0, read: 1, write: 1 };

function mount(overrides: Partial<EditorState> = {}) {
	const state = taskNote(overrides);
	state.definition.permissions ??= [writer];
	const mounted = mountEditor(state);
	stop = mounted.stop;
	return mounted;
}

const rows = (mounted: ReturnType<typeof mount>) => mounted.canvas.working.value.settings.permissions;
const writerKey = { role: "Writer", permlevel: 0, if_owner: 0 };

describe("the settings acts", () => {
	it("tick a right's prerequisites, and untick the rights that need an unticked one", async () => {
		const mounted = mount();
		await acts.run("settings.set_permission", { ...writerKey, right: "cancel", value: 1 });
		const [row] = rows(mounted);
		expect([row.cancel, row.submit, row.write]).toEqual([1, 1, 1]);
		await acts.run("settings.set_permission", { ...writerKey, right: "write", value: 0 });
		expect([rows(mounted)[0].write, rows(mounted)[0].submit, rows(mounted)[0].cancel, rows(mounted)[0].read]).toEqual([0, 0, 0, 1]);
	});

	it("add a rule with read only, and refuse a second rule for the same role and level", async () => {
		const mounted = mount();
		await acts.run("settings.add_permission", { role: "Reader", permlevel: 0, if_owner: 0 });
		const added = rows(mounted).find((row) => row.role === "Reader")!;
		expect([added.read, added.write, added.create]).toEqual([1, 0, 0]);
		await acts.perform("settings.add_permission", { role: "Reader", permlevel: 0, if_owner: 0 });
		expect(toast.error).toHaveBeenCalledWith("Reader already has a row at level 0.");
	});

	it("undo opens the tab of each change, across the Editor and Settings tabs", async () => {
		const mounted = mount();
		await acts.run("fields.set_field_property", { fieldname: "subject", property: "bold", value: 1 });
		await acts.run("settings.set_doctype_property", { property: "title_field", value: "subject" });
		mounted.tab.value = "editor";
		mounted.edits.undo();
		expect([mounted.tab.value, mounted.canvas.working.value.settings.properties.title_field]).toEqual(["settings", undefined]);
		mounted.edits.undo();
		expect(mounted.tab.value).toBe("editor");
		expect((mounted.canvas.field("subject") as { bold?: number }).bold).toBeUndefined();
	});

	it("refuse Number in order while records exist, and allow it on an empty DocType", async () => {
		mount();
		await acts.perform("settings.set_doctype_property", { property: "autoname", value: "autoincrement" });
		expect(toast.error).toHaveBeenCalledWith("Number in order can only be switched to or from while there are no records.");
		stop();
		const empty = mount({ record_count: 0 });
		await acts.run("settings.set_doctype_property", { property: "autoname", value: "autoincrement" });
		expect(empty.canvas.working.value.settings.properties.autoname).toBe("autoincrement");
	});

	it("add a mandatory naming_series field with the series in Design", async () => {
		const mounted = mount();
		await acts.run("settings.set_naming_series", { options: ["TN-.####", "NOTE-.####"], default: "NOTE-.####" });
		const field = mounted.canvas.field("naming_series")!;
		expect([field.fieldtype, field.reqd, field.options, field.default]).toEqual(["Select", 1, "TN-.####\nNOTE-.####", "NOTE-.####"]);
		expect(mounted.edits.steps).toHaveLength(1);
	});

	it("in Customize, make the rows the site's own on the first edit, and reset them to the app's", async () => {
		const app = { ...writer, write: 0 };
		const mounted = mount({ mode: "Customize", modes: ["Customize"], custom: 0, app_permissions: [app], settable_properties: ["title_field"] });
		const settings = () => mounted.canvas.working.value.settings;
		expect(settings().sitePermissions).toBe(false);
		await acts.run("settings.set_permission", { ...writerKey, right: "delete", value: 1 });
		expect([settings().sitePermissions, settings().permissions[0].delete]).toEqual([true, 1]);
		await acts.run("settings.reset_permissions", {});
		expect([settings().sitePermissions, settings().permissions[0].write, settings().permissions[0].delete]).toEqual([false, 0, 0]);
		await acts.perform("settings.set_doctype_property", { property: "track_seen", value: 1 });
		expect(toast.error).toHaveBeenCalledWith("track_seen is not a DocType setting the editor sets.");
	});
});
