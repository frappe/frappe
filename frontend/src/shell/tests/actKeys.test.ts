// The shell's act keys: a combo runs the act that holds it now, through the dispatcher, and a
// page act wins over a shell act on a shared combo.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, type App } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));
vi.mock("@framework/ui/api", () => ({
	runMethod: vi.fn(async () => ({ data: null })),
	getMeta: vi.fn(async () => ({ data: null, children: [] })),
}));

import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { resetUserRoles } from "@framework/ui/useUserRoles";
import { acts, type ActEntry, type ActScope } from "@/acts/dispatcher";
import { createRecordPage, type RecordPageHost } from "@/recordPage/createRecordPage";
import { withRegisteringSource } from "@/recordPage/context";
import { registerRecordPage, resetRegistry } from "@/recordPage/registry";
import type { AuthoredHandlers } from "@/recordPage/types";
import { ActKeys, type OpenArgument } from "../actKeys";

const apps: App[] = [];
const controllers: ReturnType<typeof createRecordPage>[] = [];
const unregisters: (() => void)[] = [];

beforeEach(() => {
	resetRegistry();
	resetDoctypeMeta();
	resetUserRoles();
});

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	for (const controller of controllers.splice(0)) controller.leave();
	for (const unregister of unregisters.splice(0)) unregister();
	document.body.innerHTML = "";
	vi.restoreAllMocks();
});

function mountKeys(openArgument?: OpenArgument) {
	const app = createApp(defineComponent({ render: () => [h("input", { name: "field" }), h(ActKeys, { openArgument })] }));
	app.mount(document.body.appendChild(document.createElement("div")));
	apps.push(app);
}

function makePage(host: Partial<RecordPageHost> = {}) {
	const controller = createRecordPage({
		doctype: "CRM Lead",
		docname: "CRM-LEAD-1",
		doc: ref({ status: "Open" }),
		saved: ref({ status: "Open" }),
		meta: ref({ name: "CRM Lead", fields: [] }),
		perms: () => ({ read: 1, write: 1 }),
		isDirty: () => false,
		activeTab: () => "details",
		activateTab: () => {},
		save: async () => {},
		reload: async () => {},
		router: {} as any,
		activityRows: () => [],
		scrollToActivity: async () => true,
		reloadActivity: async () => {},
		fileRows: () => [],
		reloadFiles: async () => {},
		...host,
	});
	controllers.push(controller);
	return controller;
}

function register(handlers: AuthoredHandlers) {
	return withRegisteringSource("crm", async () => registerRecordPage("CRM Lead", handlers));
}

function registerScope(surface: string, entries: ActEntry[]) {
	const scope: ActScope = {
		surfaces: { [surface]: () => entries },
		context: () => ({}),
		passes: () => true,
		settled: () => undefined,
		hold: async (work) => work(),
		failed: () => {},
	};
	unregisters.push(acts.register(scope));
}

async function press(combo: { key: string; ctrlKey?: boolean; shiftKey?: boolean; repeat?: boolean }, target: Element = document.body) {
	await nextTick();
	const event = new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...combo });
	target.dispatchEvent(event);
	await new Promise((resolve) => setTimeout(resolve, 0));
	return event;
}

const CTRL_SHIFT_D = { key: "d", ctrlKey: true, shiftKey: true };

describe("act keys", () => {
	it("runs an act added under an if in onRefresh only while the if holds", async () => {
		const run = vi.fn();
		await register({
			onRefresh: (page) => {
				if (page.doc.status === "Open")
					page.header.add({ name: "convert", label: "Convert", key: "Mod+Shift+D", run });
			},
		});
		const doc = ref({ status: "Open" });
		const controller = makePage({ doc });
		await controller.refresh();
		mountKeys();

		const event = await press(CTRL_SHIFT_D);
		expect(run).toHaveBeenCalledWith(controller.page, undefined);
		expect(event.defaultPrevented).toBe(true);

		doc.value = { status: "Converted" };
		await controller.refresh();
		const after = await press(CTRL_SHIFT_D);

		expect(run).toHaveBeenCalledOnce();
		expect(after.defaultPrevented).toBe(false);
	});

	it("does nothing for a hidden act, and for one whose right fails", async () => {
		const run = vi.fn();
		await register({
			onRefresh: (page) => {
				page.header.add({ name: "archive", label: "Archive", key: "Mod+Shift+D", run });
				page.header.add({ name: "purge", label: "Purge", key: "Mod+Shift+P", right: "delete", run });
				page.header.hide("archive");
			},
		});
		await makePage().refresh();
		mountKeys();

		const hidden = await press(CTRL_SHIFT_D);
		const denied = await press({ key: "p", ctrlKey: true, shiftKey: true });

		expect(run).not.toHaveBeenCalled();
		expect(hidden.defaultPrevented).toBe(false);
		expect(denied.defaultPrevented).toBe(false);
	});

	it("runs the page act over the shell act on a shared combo, with a dev warning", async () => {
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		const shellRun = vi.fn();
		const pageRun = vi.fn();
		registerScope("shell", [{ item: { name: "toggle_sidebar", key: "Mod+Shift+D", run: shellRun }, hidden: false }]);
		registerScope("header", [{ item: { name: "duplicate", key: "Mod+Shift+D", run: pageRun }, hidden: false }]);
		mountKeys();

		await press(CTRL_SHIFT_D);

		expect(pageRun).toHaveBeenCalledOnce();
		expect(shellRun).not.toHaveBeenCalled();
		expect(warn).toHaveBeenCalledWith(expect.stringContaining("header.duplicate, shell.toggle_sidebar"));
	});

	it("treats one combo spelled two ways as one combo", async () => {
		vi.spyOn(console, "warn").mockImplementation(() => {});
		const shellRun = vi.fn();
		const pageRun = vi.fn();
		registerScope("header", [{ item: { name: "duplicate", key: "mod+shift+d", run: pageRun }, hidden: false }]);
		registerScope("shell", [{ item: { name: "toggle_sidebar", key: "Shift+Mod+D", run: shellRun }, hidden: false }]);
		mountKeys();

		await press(CTRL_SHIFT_D);

		expect(pageRun).toHaveBeenCalledOnce();
		expect(shellRun).not.toHaveBeenCalled();
	});

	it("leaves a key to the dialog, popover or dropdown it is pressed in", async () => {
		const back = vi.fn();
		const save = vi.fn();
		registerScope("header", [
			{ item: { name: "back", key: "Escape", run: back }, hidden: false },
			{ item: { name: "save", key: "Mod+S", run: save }, hidden: false },
		]);
		mountKeys();
		const dialog = document.body.appendChild(document.createElement("div"));
		dialog.setAttribute("role", "dialog");
		const menu = document.body.appendChild(document.createElement("div"));
		menu.setAttribute("role", "menu");

		const escapes = [await press({ key: "Escape" }, dialog), await press({ key: "Escape" }, menu)];
		const saveInDialog = await press({ key: "s", ctrlKey: true }, dialog);

		expect(escapes.map((event) => event.defaultPrevented)).toEqual([false, false]);
		expect(saveInDialog.defaultPrevented).toBe(true);
		expect(back).not.toHaveBeenCalled();
		expect(save).not.toHaveBeenCalled();
		await press({ key: "Escape" });
		expect(back).toHaveBeenCalledOnce();
	});

	it("reads no right of an act that has no key", async () => {
		const passes = vi.fn(() => true);
		unregisters.push(
			acts.register({
				surfaces: { header: () => [{ item: { name: "convert", right: { doctype: "CRM Deal", ptype: "create" }, run: vi.fn() }, hidden: false }] },
				context: () => ({}),
				passes,
				settled: () => undefined,
				hold: async (work) => work(),
				failed: () => {},
			})
		);
		mountKeys();
		await nextTick();

		expect(passes).not.toHaveBeenCalled();
	});

	it("runs the shell act once the page that shadowed it lets go", async () => {
		const shellRun = vi.fn();
		vi.spyOn(console, "warn").mockImplementation(() => {});
		registerScope("shell", [{ item: { name: "toggle_sidebar", key: "Mod+Shift+D", run: shellRun }, hidden: false }]);
		registerScope("header", [{ item: { name: "duplicate", key: "Mod+Shift+D", run: vi.fn() }, hidden: false }]);
		mountKeys();
		unregisters.pop()!();

		await press(CTRL_SHIFT_D);

		expect(shellRun).toHaveBeenCalledOnce();
	});

	it("fires a Mod combo in a field, and never a combo that types text", async () => {
		const save = vi.fn();
		const edit = vi.fn();
		registerScope("header", [
			{ item: { name: "save", key: "Mod+S", run: save }, hidden: false },
			{ item: { name: "edit", key: "E", run: edit }, hidden: false },
		]);
		mountKeys();
		const field = document.querySelector("input[name='field']")!;

		await press({ key: "s", ctrlKey: true }, field);
		await press({ key: "e" }, field);
		await press({ key: "e" });

		expect(save).toHaveBeenCalledOnce();
		expect(edit).toHaveBeenCalledOnce();
	});

	it("runs once per press, not on the repeats of a held combo", async () => {
		const save = vi.fn();
		registerScope("header", [{ item: { name: "save", key: "Mod+S", run: save }, hidden: false }]);
		mountKeys();

		await press({ key: "s", ctrlKey: true });
		const repeat = await press({ key: "s", ctrlKey: true, repeat: true });

		expect(save).toHaveBeenCalledOnce();
		expect(repeat.defaultPrevented).toBe(true);
	});

	it("binds no key on an act with an argument until the palette opens its argument step", async () => {
		const run = vi.fn();
		const argument = { label: "User", options: () => [] };
		registerScope("header", [{ item: { name: "assign", key: "Mod+Shift+D", argument, run }, hidden: false }]);
		mountKeys();
		expect((await press(CTRL_SHIFT_D)).defaultPrevented).toBe(false);
		apps.splice(0).forEach((app) => app.unmount());

		const openArgument = vi.fn();
		mountKeys(openArgument);
		await press(CTRL_SHIFT_D);

		expect(openArgument).toHaveBeenCalledWith(expect.objectContaining({ name: "header.assign" }));
		expect(run).not.toHaveBeenCalled();
	});
});
