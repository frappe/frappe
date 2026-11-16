// Every dialog an act opens is on one list; a caller fills a form dialog but never answers a confirm.
import { describe, expect, it, vi } from "vitest";
import { dialog as frappeDialog } from "frappe-ui";
import { effectScope, ref } from "vue";

vi.mock("frappe-ui", () => ({
	dialog: {
		confirm: vi.fn(() => ({ close: vi.fn() })),
		danger: vi.fn(() => ({ close: vi.fn() })),
	},
	toast: { error: vi.fn() },
}));

import { dialogEntries } from "../dialogActs";
import { createPageDialogs, type PageDialogHost } from "../dialogs/pageDialogs";
import { readDialogs, useReadableDialog } from "../dialogs/readableDialogs";
import { shellDialog } from "../dialog";

const host: PageDialogHost = { source: () => "test", isReplaying: () => false, hold: async (work) => work() };


describe("the readable dialog list", () => {
	it("lists a page's confirm and danger with their buttons until it closes", () => {
		const dialogs = createPageDialogs(host);
		void dialogs.api.confirm({ title: "Submit?", message: "Sure?", confirmLabel: "Submit" });
		void dialogs.api.danger({ title: "Delete?" });
		const [confirm, danger] = readDialogs().slice(-2);
		expect(confirm).toMatchObject({ kind: "confirm", title: "Submit?", message: "Sure?", buttons: ["Submit", "Cancel"] });
		expect(danger).toMatchObject({ kind: "danger", title: "Delete?", buttons: ["Delete", "Cancel"] });
		expect(confirm).not.toHaveProperty("fieldnames");
		dialogs.closeAll();
		expect(readDialogs()).toEqual([]);
	});

	it("lists the shell's confirm until it is answered", async () => {
		void shellDialog().confirm({ title: "Leave?", actions: [{ label: "Stay" }, { label: "Leave" }] });
		expect(readDialogs()).toMatchObject([{ kind: "confirm", title: "Leave?", buttons: ["Stay", "Leave"] }]);
		await vi.mocked(frappeDialog.confirm).mock.lastCall![0].onCancel!();
		expect(readDialogs()).toEqual([]);
	});

	it("lists open and form dialogs, and takes them off on settle", async () => {
		const dialogs = createPageDialogs(host);
		const opened = dialogs.api.open({} as any, {}, { title: "Required fields" });
		const form = dialogs.api.form({ title: "Rename", submitLabel: "Rename" });
		expect(readDialogs()).toMatchObject([
			{ kind: "dialog", title: "Required fields" },
			{ kind: "form", title: "Rename", buttons: ["Rename"] },
		]);
		dialogs.entries.value[0].settle("done");
		await expect(opened).resolves.toBe("done");
		expect(readDialogs()).toHaveLength(1);
		dialogs.closeAll();
		await form;
		expect(readDialogs()).toEqual([]);
	});

	it("lists a component dialog while its model is open", async () => {
		const open = ref(false);
		const scope = effectScope();
		scope.run(() => useReadableDialog(open, () => ({ kind: "danger", title: "Delete 3 records?", buttons: ["Delete"] })));
		expect(readDialogs()).toEqual([]);
		open.value = true;
		await Promise.resolve();
		expect(readDialogs()).toMatchObject([{ kind: "danger", title: "Delete 3 records?" }]);
		scope.stop();
		expect(readDialogs()).toEqual([]);
	});

	it("keeps a component dialog's buttons current while it stays open", async () => {
		const open = ref(true);
		const buttons = ref(["Delete"]);
		const scope = effectScope();
		scope.run(() => useReadableDialog(open, () => ({ kind: "danger", buttons: buttons.value })));
		buttons.value = ["Close"];
		await Promise.resolve();
		expect(readDialogs()).toMatchObject([{ buttons: ["Close"] }]);
		expect(readDialogs()).toHaveLength(1);
		scope.stop();
	});
});

describe("the dialog surface", () => {
	function act(name: string) {
		return dialogEntries().find((entry) => entry.item.name === name)!.item;
	}

	it("fills, submits and closes the form in front", () => {
		const dialogs = createPageDialogs(host);
		void dialogs.api.form({ title: "Rename" });
		const submit = vi.fn();
		const close = vi.fn();
		const values: Record<string, any> = {};
		dialogs.entries.value[0].listed.handle = {
			fieldnames: () => ["new_name"],
			values: () => values,
			setValues: (next) => Object.assign(values, next),
			submit,
			close,
		};
		expect(readDialogs()[0]).toMatchObject({ fieldnames: ["new_name"] });
		expect(act("set_values").when!(null)).toBe(true);
		act("set_values").run!(null, { values: { new_name: "B" } });
		act("submit").run!(null);
		act("close").run!(null);
		expect(values).toEqual({ new_name: "B" });
		expect([submit, close].map((fn) => fn.mock.calls.length)).toEqual([1, 1]);
		dialogs.closeAll();
	});

	it("is not offered while only a confirm is open", () => {
		const dialogs = createPageDialogs(host);
		void dialogs.api.confirm({ title: "Submit?" });
		expect(act("submit").when!(null)).toBe(false);
		dialogs.closeAll();
	});
});
