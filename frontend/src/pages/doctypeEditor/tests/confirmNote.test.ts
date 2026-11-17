import { describe, expect, it, vi } from "vitest";
import { createApp, h, reactive, watch } from "vue";

vi.mock("@framework/ui/api", () => ({ getTranslations: vi.fn() }));

import { agentAsk } from "@/acts/dispatcher";
import { ListedDialogKey } from "@/shell/dialogs/readableDialogs";
import ChangeKindDialog from "../ChangeKindDialog.vue";
import ConfirmNote from "../ConfirmNote.vue";

function mountNote(listed: object) {
	const host = document.createElement("div");
	const app = createApp({ render: () => h(ConfirmNote, { kind: "danger", message: "Sure?", buttons: ["Cancel", "Delete"] }) });
	app.provide(ListedDialogKey, listed);
	app.mount(host);
	return { host, stop: () => app.unmount() };
}

describe("ConfirmNote", () => {
	it("lists the dialog's message and buttons before its kind, as a run reads the dialog the moment the kind changes", () => {
		const listed = reactive({ kind: "dialog", message: "", buttons: [] as string[] });
		const seen: unknown[] = [];
		watch(() => listed.kind, () => seen.push({ ...listed }), { flush: "sync" });

		const { stop } = mountNote(listed);

		expect(seen).toEqual([{ kind: "danger", message: "Sure?", buttons: ["Cancel", "Delete"] }]);
		stop();
	});

	it("draws the line only for an agent's call", () => {
		agentAsk.note = () => "An agent asked for this.";
		const asked = mountNote({});
		expect(asked.host.textContent).toBe("An agent asked for this.");
		asked.stop();

		agentAsk.note = () => "";
		const person = mountNote({});
		expect(person.host.textContent).toBe("");
		person.stop();
	});
});

describe("ChangeKindDialog", () => {
	const confirmButton = (initial: "single" | "child") => {
		const host = document.createElement("div");
		const props = { doctype: "Task", kind: "regular", records: 0, initial, submit: vi.fn(), close: vi.fn() };
		const app = createApp({ render: () => h(ChangeKindDialog, props) });
		app.mount(host);
		const button = host.querySelector<HTMLButtonElement>("[data-danger-confirm]")!;
		return { disabled: button.disabled, stop: () => app.unmount() };
	};

	it("keeps Change kind off for a kind the person could not pick, even when an agent filled it", () => {
		const refused = confirmButton("single");
		expect(refused.disabled).toBe(true);
		refused.stop();

		const allowed = confirmButton("child");
		expect(allowed.disabled).toBe(false);
		allowed.stop();
	});
});
