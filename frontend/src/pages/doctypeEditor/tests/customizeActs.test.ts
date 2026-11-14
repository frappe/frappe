import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { toast, runMethod } = vi.hoisted(() => ({
	toast: { error: vi.fn(), success: vi.fn() },
	runMethod: vi.fn(),
}));
vi.mock("frappe-ui", () => ({ toast }));
vi.mock("@framework/ui/api", () => ({ runMethod }));

import { acts } from "@/acts/dispatcher";
import { EXPORT_METHOD, RESET_METHOD, resetLines, type CustomizeHost } from "../customizeActs";
import type { EditorState } from "../editorSource";
import { mountEditor, taskNote } from "./editorFixture";

const COUNTS = {
	delete: { custom_fields: 2, property_setters: 1, layouts: 0 },
	keep: { custom_fields: 1, property_setters: 0, layouts: 0 },
};

let stop: () => void;
beforeEach(() => {
	runMethod.mockReset();
	toast.success.mockReset();
});
afterEach(() => stop());

function mount(state: Partial<EditorState>, customize: Partial<CustomizeHost> = {}) {
	const host: CustomizeHost = {
		developerMode: false,
		setMode: vi.fn(),
		askReset: vi.fn(async () => true as const),
		askExport: vi.fn(async () => null),
		reload: vi.fn(async () => undefined),
		...customize,
	};
	const mounted = mountEditor(taskNote({ custom: 0, app_title: "ERPNext", ...state }), { customize: host });
	stop = mounted.stop;
	return host;
}

const offered = (name: string) => acts.available().some((act) => act.name === name);

describe("the Design | Customize switch", () => {
	it("shows only when both modes are permitted", () => {
		mount({ mode: "Customize", modes: ["Customize"] });
		expect(offered("editor.set_mode")).toBe(false);
		stop();
		mount({ mode: "Customize", modes: ["Design", "Customize"] });
		expect(offered("editor.set_mode")).toBe(true);
	});

	it("opens the other mode, and stays put on the open one", async () => {
		const host = mount({ mode: "Design", modes: ["Design", "Customize"] });
		await acts.run("editor.set_mode", "Design");
		expect(host.setMode).not.toHaveBeenCalled();
		await acts.run("editor.set_mode", "Customize");
		expect(host.setMode).toHaveBeenCalledWith("Customize");
	});
});

describe("Reset all customizations", () => {
	it("is a Customize act", () => {
		mount({ mode: "Design", modes: ["Design", "Customize"] });
		expect(offered("customize.reset_all")).toBe(false);
		stop();
		mount({ mode: "Customize", modes: ["Customize"] });
		expect(offered("customize.reset_all")).toBe(true);
	});

	it("asks with the counts, then deletes and reloads", async () => {
		const host = mount({ mode: "Customize", modes: ["Customize"] });
		runMethod.mockResolvedValueOnce({ data: COUNTS }).mockResolvedValueOnce({ data: COUNTS });
		await acts.run("customize.reset_all");
		expect(host.askReset).toHaveBeenCalledWith(expect.objectContaining({ doctype: "Task Note" }), COUNTS);
		expect(runMethod.mock.calls).toEqual([
			[RESET_METHOD, { doctype: "Task Note" }],
			[RESET_METHOD, { doctype: "Task Note", confirm: 1 }],
		]);
		expect(host.reload).toHaveBeenCalled();
	});

	it("deletes nothing when the reader cancels", async () => {
		const host = mount({ mode: "Customize", modes: ["Customize"] }, { askReset: async () => null });
		runMethod.mockResolvedValueOnce({ data: COUNTS });
		await acts.run("customize.reset_all");
		expect(runMethod).toHaveBeenCalledTimes(1);
		expect(host.reload).not.toHaveBeenCalled();
	});

	it("lists what it removes", () => {
		expect(resetLines(COUNTS.delete)).toEqual(["2 custom fields", "1 property change"]);
		expect(resetLines({ custom_fields: 0, property_setters: 0, layouts: 1 })).toEqual(["1 site layout"]);
	});
});

describe("Export customizations", () => {
	it("is offered in developer mode only", () => {
		mount({ mode: "Customize", modes: ["Customize"] });
		expect(offered("customize.export")).toBe(false);
		stop();
		mount({ mode: "Customize", modes: ["Design", "Customize"] }, { developerMode: true });
		expect(offered("customize.export")).toBe(true);
	});

	it("writes the file with the reader's answers", async () => {
		const answers = { module: "Desk", sync_on_migrate: true, with_permissions: false };
		mount({ mode: "Customize", modes: ["Design", "Customize"] }, { developerMode: true, askExport: async () => answers });
		runMethod.mockResolvedValueOnce({ data: COUNTS }).mockResolvedValueOnce({ data: "frappe/desk/custom/task_note.json" });
		await acts.run("customize.export");
		expect(runMethod).toHaveBeenCalledWith(RESET_METHOD, { doctype: "Task Note" });
		expect(runMethod).toHaveBeenCalledWith(EXPORT_METHOD, { doctype: "Task Note", ...answers });
		expect(toast.success).toHaveBeenCalledWith("Exported to frappe/desk/custom/task_note.json.");
	});
});
