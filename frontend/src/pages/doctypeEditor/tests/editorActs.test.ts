import { describe, expect, it } from "vitest";
import { effectScope, ref } from "vue";
import { acts } from "@/acts/dispatcher";
import { useEditorActs, type EditorActsHost } from "../editorActs";
import { EditorSave } from "../editorSave";
import { PendingEdits, type EditorTab } from "../pendingEdits";

const VERSION = { doctype: "2026-11-13 10:00:00", layouts: {}, app_layouts: {} };

function mount() {
	const tab = ref<EditorTab>("editor");
	const previewed: (string | null)[] = [];
	const edits = new PendingEdits(
		{ doctype: "Note", mode: "Design", base_version: VERSION },
		(opened) => (tab.value = opened),
	);
	const unused = async () => {
		throw new Error("no canvas to reload");
	};
	const host: EditorActsHost = {
		tab,
		edits,
		canvas: () => null,
		find: () => undefined,
		previewRecord: (name) => previewed.push(name),
		recordOptions: async () => [],
		save: new EditorSave({ edits, canvas: () => null, reload: unused, created: unused }),
		openList: () => undefined,
	};
	const scope = effectScope();
	scope.run(() => useEditorActs(host));
	return { host, tab, previewed, stop: () => scope.stop() };
}

describe("the editor's acts", () => {
	it("are named <surface>.<item> on the editor surface", () => {
		const { host, stop } = mount();
		host.edits.stage({ act: "canvas.add_tab", value: {}, tab: "editor" });
		host.edits.undo();
		const names = acts.available().map((act) => act.name).filter((name) => name.startsWith("editor."));
		expect(names.sort()).toEqual([
			"editor.find",
			"editor.open_tab",
			"editor.preview_record",
			"editor.redo",
		]);
		stop();
		expect(acts.find("editor.find")).toBeUndefined();
	});

	it("take one value", async () => {
		const { tab, previewed, stop } = mount();
		await acts.run("editor.open_tab", "settings");
		expect(tab.value).toBe("settings");
		await acts.run("editor.preview_record", null);
		expect([tab.value, previewed]).toEqual(["preview", [null]]);
		stop();
	});

	it("undo opens the tab of the change", async () => {
		const { host, tab, stop } = mount();
		host.edits.stage({ act: "settings.set_property", value: {}, tab: "settings" });
		await acts.run("editor.undo");
		expect(tab.value).toBe("settings");
		expect(acts.find("editor.undo")).toBeUndefined();
		stop();
	});

	it("leave Mod+Z to Preview's fields", () => {
		const { host, tab, stop } = mount();
		host.edits.stage({ act: "settings.set_property", value: {}, tab: "settings" });
		tab.value = "preview";
		expect(acts.available().map((act) => act.name)).not.toContain("editor.undo");
		tab.value = "editor";
		expect(acts.available().map((act) => act.name)).toContain("editor.undo");
		stop();
	});
});
