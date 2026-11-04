// One record opened as a dialog: what it loads, what Save sends, what a reader without the write
// right or the read right sees, and the record script that runs in it. The server answers through a faked fetch.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, inject, nextTick, watch, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

const discard = vi.hoisted(() => vi.fn());
vi.mock("@/pages/record/discardChanges", () => ({ discardChanges: discard }));

// The loader a `pages.json` dialog entry's body gives; null for a doctype with no body.
const bodyLoader = vi.hoisted(() => ({ current: null as null | (() => Promise<unknown>) }));
vi.mock("@/contributions/registry", async (importOriginal) => ({
	...((await importOriginal()) as object),
	recordDialogBody: () => bodyLoader.current ?? undefined,
}));

// A passthrough Dialog that ends its leave at once, so the test reads the form, not reka-ui.
vi.mock("frappe-ui", () => ({
	Dialog: defineComponent({
		props: { open: { type: Boolean, default: true }, title: String, size: String },
		emits: ["update:open", "after-leave"],
		setup(props, { slots, emit }) {
			watch(
				() => props.open,
				(open) => !open && emit("after-leave")
			);
			return () =>
				props.open
					? h("div", { "data-dialog": "", role: "dialog" }, [
							h("header", slots.title?.() ?? h("h3", props.title)),
							h("button", { onClick: () => emit("update:open", false) }, "Close"),
							h("div", slots.default?.()),
							h("div", slots.actions?.()),
						])
					: null;
		},
	}),
	Button: defineComponent({
		props: { label: String, loading: Boolean, disabled: Boolean, tooltip: String },
		setup(props, { attrs }) {
			return () => h("button", { ...attrs, disabled: props.disabled }, props.label ?? props.tooltip);
		},
	}),
	Dropdown: defineComponent({
		props: { options: { type: Array, default: () => [] } },
		setup: (props, { slots }) => () =>
			h("div", [
				slots.default?.(),
				...(props.options as any[])
					.flatMap((option) => option.options ?? [option])
					.map((option) => h("button", { onClick: option.onClick }, option.label)),
			]),
	}),
	ErrorMessage: defineComponent({
		props: { message: String },
		setup: (props) => () => h("p", { class: "error" }, props.message),
	}),
	Skeleton: defineComponent({ setup: () => () => h("div") }),
	createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
	frappeRequest: vi.fn(),
	call: vi.fn(),
	toast: { success: vi.fn(), error: vi.fn() },
	dialog: { confirm: vi.fn(), danger: vi.fn() },
}));

// The real FormLayout is exercised in Chrome; this one draws an input per field and owns the doc.
vi.mock("@framework/ui/FormLayout", async (importOriginal) => {
	const { FieldErrorsKey } = await import("@framework/ui/fields/types");
	return {
		...((await importOriginal()) as object),
		FormLayout: defineComponent({
			props: { layout: { type: Array, required: true }, doc: { type: Object, required: true } },
			emits: ["update:doc"],
			setup(props, { emit }) {
				const errors = inject(FieldErrorsKey, null);
				const fields = () =>
					(props.layout as any[]).flatMap((tab) =>
						tab.sections.flatMap((section: any) => section.columns.flatMap((column: any) => column.fields))
					).filter((field: any) => !field.hidden && !field.override?.hidden);
				return () =>
					h(
						"form",
						fields().map((field: any) =>
							h("input", {
								name: field.fieldname,
								value: props.doc[field.fieldname] ?? "",
								"data-error": errors?.value[field.fieldname],
								onInput: (event: Event) =>
									emit("update:doc", { ...props.doc, [field.fieldname]: (event.target as HTMLInputElement).value }),
							})
						)
					);
			},
		}),
	};
});

import type { Boot } from "@/boot";
import { registerRecordPage, resetRegistry } from "@/recordPage/registry";
import { resetFormLayouts } from "@/recordPage";
import { closeRecordDialogs, openRecordDialog, recordDialog, recordDialogRequests, recordDialogWrite, registerRecordDialog } from "@/shell/recordDialog";
import type { Session } from "@framework/ui/api";
import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { resetSession, setSession } from "@framework/ui/useSession";
import RecordDialog from "../RecordDialog.vue";

const LAYOUTS = "/api/v2/method/frappe.desk.doctype.form_layout.form_layout.get_form_layouts";
const SESSION: Session = {
	user: { name: "test@example.com", full_name: "Test", email: "test@example.com", user_image: null, document_follow_notify: false },
	roles: ["Sales User"],
	lang: "en",
	timezone: "Asia/Kolkata",
	defaults: {},
};
const boot = { app: "crm", shell_base: "/apps/crm", prefixes: { crm: { app: "crm", modular: false } } } as unknown as Boot;
const LEAD = { doctype: "Lead", name: "LEAD-1", title: "Big deal", source: "Web", company: "Acme", modified: "2026-11-04 10:00:00.000000" };

interface Server {
	get: () => Response;
	permissions: Record<string, unknown>;
	write: (body: Record<string, any>) => Response;
}

const fetchMock = vi.fn<typeof fetch>();
let server: Server;
const apps: App[] = [];

function json(body: unknown, status = 200) {
	return new Response(JSON.stringify(body), { status });
}

function leadServer(): Server {
	const server: Server = {
		permissions: { read: 1, write: 1, delete: 1 },
		get: () => json({ data: LEAD, permissions: server.permissions }),
		write: (body) => json({ data: { ...LEAD, ...body, modified: "2026-11-04 10:05:00.000000" } }),
	};
	return server;
}

beforeEach(() => {
	resetDoctypeMeta();
	resetFormLayouts();
	resetRegistry();
	clearDataCache();
	setSession(SESSION);
	discard.mockReset();
	server = leadServer();
	recordDialogWrite.value = null;
	bodyLoader.current = null;
	fetchMock.mockReset().mockImplementation(async (url, init) => {
		const path = new URL(String(url), "http://x").pathname;
		if (path.endsWith("/meta"))
			return json({
				data: {
					name: "Lead",
					fields: [
						{ fieldname: "title", fieldtype: "Data", label: "Title", reqd: 1 },
						{ fieldname: "source", fieldtype: "Data", label: "Source" },
						{ fieldname: "company", fieldtype: "Data", label: "Company" },
					],
					permissions: [{ role: "Sales User", permlevel: 0, read: 1, write: 1 }],
				},
			});
		if (path === LAYOUTS)
			return json({
				data: {
					layouts: [],
					fallback: [{ sections: [{ columns: [{ fields: ["title", "source", "company"] }] }] }],
					dialog: true,
				},
			});
		if (path === "/api/v2/document/Lead/LEAD-1")
			return init?.method && init.method !== "GET" ? server.write(JSON.parse(String(init.body))) : server.get();
		return json({ errors: [{ type: "NotFound", message: path }] }, 404);
	});
	vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	closeRecordDialogs("");
	resetSession();
	vi.unstubAllGlobals();
});

async function settle() {
	for (let turn = 0; turn < 5; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

async function open() {
	registerRecordDialog(RecordDialog);
	expect(recordDialog()).toBeTruthy();
	openRecordDialog("Lead", "LEAD-1", "/lead");
	const request = recordDialogRequests.value.at(-1)!;
	const router = createRouter({ history: createMemoryHistory(), routes: [{ path: "/:any(.*)", component: { render: () => null } }] });
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(RecordDialog, { request });
	app.use(router).provide("boot", boot);
	app.mount(root);
	apps.push(app);
	await settle();
	return root;
}

function input(root: HTMLElement, fieldname: string) {
	return root.querySelector<HTMLInputElement>(`input[name='${fieldname}']`);
}

function button(root: HTMLElement, label: string) {
	return [...root.querySelectorAll("button")].find((element) => element.textContent?.trim() === label);
}

async function click(root: HTMLElement, label: string) {
	button(root, label)!.dispatchEvent(new MouseEvent("click"));
	await settle();
}

async function type(root: HTMLElement, fieldname: string, value: string) {
	const field = input(root, fieldname)!;
	field.value = value;
	field.dispatchEvent(new Event("input"));
	await settle();
}

function labels(element: Element | null | undefined) {
	return [...(element?.querySelectorAll("button") ?? [])].map((button) => button.textContent?.trim() || button.getAttribute("aria-label"));
}

function ctrlS() {
	document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "s", ctrlKey: true, bubbles: true, cancelable: true }));
	return settle();
}

function writes() {
	return fetchMock.mock.calls
		.filter(([, init]) => init?.method && init.method !== "GET")
		.map(([url, init]) => ({ method: init!.method, path: new URL(String(url), "http://x").pathname, body: JSON.parse(String(init!.body)) }));
}

describe("the record dialog", () => {
	it("shows the record titled by its name, with the Quick Entry fields filled", async () => {
		const root = await open();

		expect(root.querySelector("h3")!.textContent).toBe("LEAD-1");
		expect(input(root, "title")!.value).toBe("Big deal");
		expect(input(root, "company")!.value).toBe("Acme");
		expect(button(root, "Save")).toBeTruthy();
		expect(button(root, "Delete")).toBeTruthy();
		expect(button(root, "Edit full form")).toBeUndefined();
	});

	it("draws the menu in the header beside the close button, and only Save in the footer", async () => {
		const root = await open();

		expect(labels(root.querySelector("header"))).toEqual(["More", "Copy link", "Delete"]);
		expect(labels(root.querySelector("[data-dialog] > div:last-child"))).toEqual(["Save"]);
		expect(root.querySelector("h3")!.id).not.toBe("");
		expect(root.querySelector("[role=dialog]")!.getAttribute("aria-labelledby")).toBe(root.querySelector("h3")!.id);
	});

	it("saves the edited record, announces the write and closes", async () => {
		const root = await open();

		await type(root, "title", "Bigger deal");
		await click(root, "Save");

		expect(writes()).toHaveLength(1);
		expect(writes()[0]).toMatchObject({ method: "PATCH", path: "/api/v2/document/Lead/LEAD-1" });
		expect(writes()[0].body).toMatchObject({ name: "LEAD-1", title: "Bigger deal" });
		expect(recordDialogWrite.value).toEqual({ doctype: "Lead" });
		expect(root.querySelector("[data-dialog]")).toBeNull();
	});

	it("draws no Save and no Delete for a reader without the write and delete rights", async () => {
		server.permissions = { read: 1 };
		const root = await open();

		expect(input(root, "title")!.value).toBe("Big deal");
		expect(button(root, "Save")).toBeUndefined();
		expect(button(root, "Delete")).toBeUndefined();
		expect(button(root, "Copy link")).toBeTruthy();
	});

	it("says so and draws no form when the reader may not read the record", async () => {
		server.permissions = { read: 0 };
		const root = await open();

		expect(root.querySelector(".error")!.textContent).toBe("You do not have permission to open this record");
		expect(root.querySelector("form")).toBeNull();
	});

	it("says so and draws no form when the server refuses the read", async () => {
		server.get = () => json({ errors: [{ type: "PermissionError", message: "No" }] }, 403);
		const root = await open();

		expect(root.querySelector(".error")!.textContent).toBe("You do not have permission to open this record");
		expect(root.querySelector("form")).toBeNull();
		expect(button(root, "Save")).toBeUndefined();
		expect(labels(root.querySelector("header"))).toContain("Copy link");
	});

	it("runs the record script: a hidden field is not drawn and beforeSave changes what is sent", async () => {
		registerRecordPage("Lead", {
			onRefresh: (page: any) => page.fields.hide("source"),
			beforeSave: (page: any) => void (page.doc.company = "Stamped"),
		});
		const root = await open();

		expect(input(root, "source")).toBeNull();
		await type(root, "title", "Bigger deal");
		await click(root, "Save");

		expect(writes()[0].body).toMatchObject({ title: "Bigger deal", company: "Stamped" });
	});

	it("sends nothing while a mandatory field is empty, and marks it", async () => {
		const root = await open();

		await type(root, "title", "");
		await click(root, "Save");

		expect(writes()).toEqual([]);
		expect(input(root, "title")!.getAttribute("data-error")).toBe("Title is required");
		expect(root.querySelector("[data-dialog]")).not.toBeNull();
	});

	it("marks the fields a refused save names and stays open with the typed values", async () => {
		server.write = () =>
			json(
				{
					errors: [
						{
							type: "ValidationError",
							message: "Source is not valid",
							field_errors: [{ fieldname: "source", message: "Source is not valid" }],
						},
					],
				},
				417
			);
		const root = await open();

		await type(root, "title", "Bigger deal");
		await click(root, "Save");

		expect(input(root, "source")!.getAttribute("data-error")).toBe("Source is not valid");
		expect(input(root, "title")!.value).toBe("Bigger deal");
		expect(recordDialogWrite.value).toBeNull();
		expect(root.querySelector("[data-dialog]")).not.toBeNull();
	});

	it("saves on Ctrl+S after a refused save, when focus has left the dialog", async () => {
		server.write = () => json({ errors: [{ type: "ValidationError", message: "Source is not valid" }] }, 417);
		const root = await open();
		await type(root, "title", "Bigger deal");
		await click(root, "Save");
		expect(writes()).toHaveLength(1);

		document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "s", ctrlKey: true, bubbles: true, cancelable: true }));
		await settle();

		expect(writes()).toHaveLength(2);
	});

	it("closes at once when nothing changed, without asking", async () => {
		const root = await open();

		await click(root, "Close");

		expect(discard).not.toHaveBeenCalled();
		expect(root.querySelector("[data-dialog]")).toBeNull();
	});

	it("asks before closing with edits, and keeps editing on No", async () => {
		discard.mockResolvedValue(false);
		const root = await open();

		await type(root, "title", "Bigger deal");
		await click(root, "Close");

		expect(discard).toHaveBeenCalledOnce();
		expect(root.querySelector("[data-dialog]")).not.toBeNull();
		expect(input(root, "title")!.value).toBe("Bigger deal");
	});

	it("closes after the reader chooses to discard", async () => {
		discard.mockResolvedValue(true);
		const root = await open();

		await type(root, "title", "Bigger deal");
		await click(root, "Close");

		expect(root.querySelector("[data-dialog]")).toBeNull();
		expect(writes()).toEqual([]);
	});
});

describe("the record dialog's body", () => {
	// A read-only summary: it reads the record from `page`, saves through it, and offers the form.
	const Summary = defineComponent({
		props: { page: { type: Object, required: true }, edit: { type: Function, required: true } },
		setup: (props) => () =>
			h("section", { "data-body": "" }, [
				h("p", `${props.page.doc.title} from ${props.page.doc.source}`),
				h("button", { onClick: () => ((props.page.doc.source = "Phone"), props.page.save()) }, "Mark as phone"),
				h("button", { onClick: () => props.edit() }, "Edit"),
			]),
	});

	beforeEach(() => {
		bodyLoader.current = async () => ({ default: Summary });
	});

	it("is drawn in place of the form, inside the dialog's frame", async () => {
		const root = await open();

		expect(root.querySelector("[data-body] p")!.textContent).toBe("Big deal from Web");
		expect(root.querySelector("form")).toBeNull();
		expect(root.querySelector("h3")!.textContent).toBe("LEAD-1");
		expect(button(root, "Delete")).toBeTruthy();
	});

	it("saves the record through the page it is given", async () => {
		const root = await open();

		await click(root, "Mark as phone");

		expect(writes()).toHaveLength(1);
		expect(writes()[0]).toMatchObject({ method: "PATCH", path: "/api/v2/document/Lead/LEAD-1" });
		expect(writes()[0].body).toMatchObject({ name: "LEAD-1", source: "Phone" });
		expect(recordDialogWrite.value).toEqual({ doctype: "Lead" });
	});

	it("gives way to the form when it asks, and keeps the record", async () => {
		const root = await open();

		await click(root, "Edit");

		expect(root.querySelector("[data-body]")).toBeNull();
		expect(input(root, "title")!.value).toBe("Big deal");
		expect(button(root, "Save")).toBeTruthy();
	});

	it("falls back to the form, with the error, when the body fails to load", async () => {
		bodyLoader.current = async () => {
			throw new Error("chunk missing");
		};
		const root = await open();

		expect(root.querySelector(".error")!.textContent).toContain("chunk missing");
		expect(input(root, "title")!.value).toBe("Big deal");
	});

	describe("with a header of its own", () => {
		const calls: string[] = [];
		// A call summary: its own title, an Edit icon button, two menu rows and no Save.
		const Headed = defineComponent({
			props: {
				page: { type: Object, required: true },
				edit: { type: Function, required: true },
				header: { type: Function, required: true },
			},
			setup(props) {
				props.header(() => ({
					title: `Call with ${props.page.doc.title}`,
					buttons: [{ label: "Edit call", icon: "lucide-pencil", onClick: () => props.edit() }],
					menu: [
						{ label: "Add note", icon: "lucide-notebook-pen", onClick: () => calls.push("note") },
						{ label: "Add task", icon: "lucide-square-check", onClick: () => calls.push("task") },
					],
					save: false,
				}));
				return () =>
					h("section", { "data-body": "" }, [
						h("button", { onClick: () => (props.page.doc.title = "Changed") }, "Rename"),
					]);
			},
		});

		beforeEach(() => {
			calls.length = 0;
			bodyLoader.current = async () => ({ default: Headed });
		});

		it("shows its title, its buttons and its menu rows above the record's, and no Save", async () => {
			const root = await open();

			expect(root.querySelector("h3")!.textContent!.trim()).toBe("Call with Big deal");
			expect(labels(root.querySelector("header"))).toEqual(["Edit call", "More", "Add note", "Add task", "Copy link", "Delete"]);
			expect(button(root, "Save")).toBeUndefined();

			await click(root, "Add task");
			expect(calls).toEqual(["task"]);
		});

		it("sends nothing on Ctrl+S while it shows, even with a change", async () => {
			const root = await open();
			await click(root, "Rename");

			await ctrlS();

			expect(writes()).toHaveLength(0);
			expect(root.querySelector("[data-dialog]")).toBeTruthy();
		});

		it("gives the form back the record's name, the record's menu and Save on Edit", async () => {
			const root = await open();

			await click(root, "Edit call");

			expect(root.querySelector("h3")!.textContent!.trim()).toBe("LEAD-1");
			expect(labels(root.querySelector("header"))).toEqual(["More", "Copy link", "Delete"]);
			expect(button(root, "Save")).toBeTruthy();
			await type(root, "title", "Bigger deal");
			await ctrlS();
			expect(writes()).toHaveLength(1);
		});
	});
});
