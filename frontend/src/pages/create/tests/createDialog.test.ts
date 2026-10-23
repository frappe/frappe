// One Create request: the Quick Entry dialog or the full-page new record, the insert it sends,
// and what the caller gets back. The server answers through a faked fetch.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, watch, type App } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

// A passthrough Dialog that ends its leave at once, so the test reads the form, not reka-ui.
vi.mock("frappe-ui", () => ({
	Dialog: defineComponent({
		props: {
			open: { type: Boolean, default: true },
			title: String,
			showCloseButton: { type: Boolean, default: true },
		},
		emits: ["update:open", "after-leave"],
		setup(props, { slots, emit }) {
			watch(
				() => props.open,
				(open) => !open && emit("after-leave")
			);
			return () =>
				props.open
					? h("div", { "data-dialog": "", role: "dialog" }, [
							h("h2", props.title),
							props.showCloseButton
								? h("button", { onClick: () => emit("update:open", false) }, "Close")
								: null,
							h("div", slots.default?.()),
							h("div", slots.actions?.()),
						])
					: null;
		},
	}),
	Button: defineComponent({
		props: { label: String, loading: Boolean, disabled: Boolean },
		setup(props, { attrs }) {
			return () => h("button", { ...attrs, disabled: props.disabled }, props.label);
		},
	}),
	ErrorMessage: defineComponent({
		props: { message: String },
		setup: (props) => () => h("p", { class: "error" }, props.message),
	}),
	Skeleton: defineComponent({ setup: () => () => h("div", { class: "fui-skeleton" }) }),
	createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
	frappeRequest: vi.fn(),
	call: vi.fn(),
	toast: { success: vi.fn(), error: vi.fn() },
	dialog: { confirm: vi.fn(), danger: vi.fn() },
}));

// The real FormLayout is exercised in Chrome; this one draws an input per field and owns the doc.
vi.mock("@framework/ui/components/FormLayout", () => ({
	FormLayout: defineComponent({
		props: { layout: { type: Array, required: true }, doc: { type: Object, required: true } },
		emits: ["update:doc"],
		setup(props, { emit }) {
			const fields = () =>
				(props.layout as any[]).flatMap((tab) =>
					tab.sections.flatMap((section: any) => section.columns.flatMap((column: any) => column.fields))
				);
			return () =>
				h(
					"form",
					fields().map((field: any) =>
						h("input", {
							name: field.fieldname,
							value: props.doc[field.fieldname] ?? "",
							onInput: (event: Event) =>
								emit("update:doc", { ...props.doc, [field.fieldname]: (event.target as HTMLInputElement).value }),
						})
					)
				);
		},
	}),
}));

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { resetFormLayouts } from "@/recordPage";
import { registerShell, routeFor } from "@/router/routeFor";
import { closeCreates, createRequests, openCreate, registerCreateDialog, type CreatedDoc } from "@/shell/create";
import type { Session } from "@framework/ui/api";
import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetSession, setSession } from "@framework/ui/composables/useSession";
import CreateDialog from "../CreateDialog.vue";

const LAYOUTS = "/api/v2/method/frappe.desk.doctype.form_layout.form_layout.get_form_layouts";
const NEW_DOC = "/api/v2/method/frappe.desk.form.load.get_new_doc";

const SESSION: Session = {
	user: { name: "test@example.com", full_name: "Test", email: "test@example.com", user_image: null, document_follow_notify: false },
	roles: ["Sales User"],
	lang: "en",
	timezone: "Asia/Kolkata",
	defaults: {},
};

const addresses = new Addresses({
	doctypes: { Lead: ["lead", "crm"], Territory: ["territory", "crm"] },
	modules: { crm: "CRM" },
});
const boot = { app: "crm", shell_base: "/apps/crm", prefixes: { crm: { app: "crm", modular: false } } } as unknown as Boot;

interface Server {
	meta: Record<string, unknown>;
	layouts: { layouts: unknown[]; fallback: unknown; dialog: boolean };
	newDoc: () => Promise<Record<string, unknown>>;
	newDocFails?: boolean;
	layoutsFail?: boolean;
	insert: (body: Record<string, unknown>) => Response | Promise<Response>;
}

const fetchMock = vi.fn<typeof fetch>();
let server: Server;
let router: Router;
const apps: App[] = [];

function json(body: unknown, status = 200) {
	return new Response(JSON.stringify(body), { status });
}

function leadServer(): Server {
	return {
		meta: {
			name: "Lead",
			autoname: "naming_series:",
			fields: [
				{ fieldname: "title", fieldtype: "Data", label: "Title", reqd: 1 },
				{ fieldname: "status", fieldtype: "Select", label: "Status", options: "Open\nClosed" },
				{ fieldname: "source", fieldtype: "Data", label: "Source" },
				{ fieldname: "company", fieldtype: "Data", label: "Company" },
			],
			permissions: [{ role: "Sales User", permlevel: 0, read: 1, write: 1, create: 1 }],
		},
		layouts: {
			layouts: [],
			fallback: [{ sections: [{ columns: [{ fields: ["title", "status", "source"] }] }] }],
			dialog: true,
		},
		newDoc: async () => ({ doctype: "Lead", name: "new-lead-1", __islocal: 1, status: "Open" }),
		insert: (body) => json({ data: { ...body, name: "LEAD-0001", doctype: "Lead" } }),
	};
}

/** The insert requests the dialog sent, their bodies parsed. */
function inserts() {
	return fetchMock.mock.calls
		.filter(([, init]) => init?.method === "POST")
		.map(([url, init]) => ({ path: new URL(String(url), "http://x").pathname, body: JSON.parse(String(init!.body)) }));
}

beforeEach(() => {
	resetDoctypeMeta();
	resetFormLayouts();
	clearDataCache();
	setSession(SESSION);
	registerCreateDialog(CreateDialog);
	closeCreates();
	server = leadServer();
	fetchMock.mockReset().mockImplementation(async (url, init) => {
		const path = new URL(String(url), "http://x").pathname;
		if (path.endsWith("/meta")) return json({ data: server.meta });
		if (path === LAYOUTS)
			return server.layoutsFail
				? json({ errors: [{ type: "ServerError", message: "Layouts are down" }] }, 500)
				: json({ data: server.layouts });
		if (path === NEW_DOC)
			return server.newDocFails
				? json({ errors: [{ type: "PermissionError", message: "No create right" }] }, 403)
				: json({ data: await server.newDoc() });
		if (init?.method === "POST" && path.startsWith("/api/v2/document/"))
			return server.insert(JSON.parse(String(init.body)));
		return json({ errors: [{ type: "NotFound", message: path }] }, 404);
	});
	vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	document.body.innerHTML = "";
	closeCreates();
	resetSession();
	vi.unstubAllGlobals();
});

async function settle() {
	for (let turn = 0; turn < 4; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

/** Opens Create the way a caller does and mounts the dialog the shell would draw for it. */
async function open(doctype: string, values?: Record<string, unknown>) {
	router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/:doctype", name: "list", component: { render: () => null } },
			{ path: "/:doctype/new", name: "new-record", component: { render: () => null } },
			{ path: "/:doctype/:name", name: "record", component: { render: () => null } },
		],
	});
	registerShell({ boot, addresses, router });
	await router.push(routeFor(doctype));
	const answer = { settled: false, doc: undefined as CreatedDoc | null | undefined };
	void openCreate(doctype, { values }).then((doc) => Object.assign(answer, { settled: true, doc }));
	const request = createRequests.value.at(-1)!;
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(CreateDialog, { request });
	app.use(router);
	app.mount(root);
	apps.push(app);
	await settle();
	return { root, answer };
}

function input(root: HTMLElement, fieldname: string) {
	return root.querySelector<HTMLInputElement>(`input[name='${fieldname}']`)!;
}

async function type(root: HTMLElement, fieldname: string, value: string) {
	const field = input(root, fieldname);
	field.value = value;
	field.dispatchEvent(new Event("input"));
	await settle();
}

function button(root: HTMLElement, label: string) {
	return [...root.querySelectorAll("button")].find((element) => element.textContent?.trim() === label);
}

async function click(root: HTMLElement, label: string) {
	button(root, label)!.dispatchEvent(new MouseEvent("click"));
	await settle();
}

describe("dialog or full page", () => {
	it("shows the Quick Entry form titled New {doctype} when the server says dialog", async () => {
		const { root, answer } = await open("Lead");

		expect(root.querySelector("h2")!.textContent).toBe("New Lead");
		expect([...root.querySelectorAll("input")].map((field) => field.name)).toEqual(["title", "status", "source"]);
		expect(button(root, "Save")).toBeTruthy();
		expect(button(root, "Edit full form")).toBeTruthy();
		expect(answer.settled).toBe(false);
		expect(createRequests.value).toHaveLength(1);
	});

	it("goes to the full-page new record with the caller's values when the server says no dialog", async () => {
		server.layouts = { ...server.layouts, dialog: false };
		const { root, answer } = await open("Lead", { company: "Acme", source: "" });

		expect(root.querySelector("[data-dialog]")).toBeNull();
		expect(answer).toEqual({ settled: true, doc: null });
		expect(createRequests.value).toEqual([]);
		expect(router.currentRoute.value.fullPath).toBe("/lead/new?company=Acme");
		expect(inserts()).toEqual([]);
	});
});

describe("saving", () => {
	it("posts the form data over the caller's values and resolves with the saved record", async () => {
		const { root, answer } = await open("Lead", { company: "Acme" });

		await type(root, "title", "Big deal");
		await click(root, "Save");

		expect(inserts()).toEqual([
			{ path: "/api/v2/document/Lead", body: { company: "Acme", title: "Big deal", status: "Open", source: null } },
		]);
		expect(answer.settled).toBe(true);
		expect(answer.doc).toMatchObject({ name: "LEAD-0001", title: "Big deal", company: "Acme" });
		expect(root.querySelector("[data-dialog]")).toBeNull();
		expect(createRequests.value).toEqual([]);
	});

	it("never sends a name the caller passed", async () => {
		const { root } = await open("Lead", { name: "LEAD-9", title: "Big deal" });

		await click(root, "Save");

		expect(inserts()).toHaveLength(1);
		expect(inserts()[0].body).not.toHaveProperty("name");
		expect(inserts()[0].body).toMatchObject({ title: "Big deal" });
	});

	it("asks a prompt-named doctype for the name and sends it as __newname", async () => {
		server.meta = {
			name: "Territory",
			autoname: "Prompt",
			fields: [{ fieldname: "parent_territory", fieldtype: "Data", label: "Parent Territory" }],
		};
		server.layouts = { layouts: [], fallback: [], dialog: true };
		const { root, answer } = await open("Territory");

		expect([...root.querySelectorAll("input")].map((field) => field.name)).toEqual(["__newname"]);
		await click(root, "Save");
		expect(inserts()).toEqual([]);
		expect(root.querySelector(".error")!.textContent).toBe("Please fill in Territory Name");

		await type(root, "__newname", "North");
		await click(root, "Save");

		expect(inserts()).toEqual([{ path: "/api/v2/document/Territory", body: { __newname: "North" } }]);
		expect(answer.settled).toBe(true);
	});

	it("sends nothing while a mandatory field is empty, and says which", async () => {
		const { root, answer } = await open("Lead");

		await click(root, "Save");

		expect(inserts()).toEqual([]);
		expect(root.querySelector(".error")!.textContent).toBe("Please fill in Title");
		expect(answer.settled).toBe(false);
		expect(root.querySelector("[data-dialog]")).not.toBeNull();
	});

	it("stays open with the server's message and the typed values when the insert fails", async () => {
		server.insert = () => json({ errors: [{ type: "ValidationError", message: "Title must be unique" }] }, 417);
		const { root, answer } = await open("Lead");

		await type(root, "title", "Big deal");
		await click(root, "Save");

		expect(inserts()).toHaveLength(1);
		expect(root.querySelector(".error")!.textContent).toBe("Title must be unique");
		expect(input(root, "title").value).toBe("Big deal");
		expect(answer.settled).toBe(false);
		expect(createRequests.value).toHaveLength(1);
		expect(button(root, "Save")!.disabled).toBe(false);
	});

	it("saves on Ctrl+Enter and on Cmd+Enter inside the form", async () => {
		const { root, answer } = await open("Lead");
		await type(root, "title", "Big deal");

		input(root, "title").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", ctrlKey: true, bubbles: true }));
		await settle();

		expect(inserts()).toHaveLength(1);
		expect(answer.settled).toBe(true);

		const second = await open("Lead");
		await type(second.root, "title", "Other deal");
		input(second.root, "title").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", metaKey: true, bubbles: true }));
		await settle();

		expect(inserts()).toHaveLength(2);
		expect(second.answer.settled).toBe(true);
	});

	it("does not save on a plain Enter", async () => {
		const { root, answer } = await open("Lead");
		await type(root, "title", "Big deal");

		input(root, "title").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
		await settle();

		expect(inserts()).toEqual([]);
		expect(answer.settled).toBe(false);
	});
});

describe("Edit full form", () => {
	it("goes to the full-page new record with the caller's and the typed values, and resolves null", async () => {
		const { root, answer } = await open("Lead", { company: "Acme" });

		await type(root, "title", "Big deal");
		await click(root, "Edit full form");

		expect(answer).toEqual({ settled: true, doc: null });
		expect(router.currentRoute.value.path).toBe("/lead/new");
		expect(router.currentRoute.value.query).toEqual({ company: "Acme", title: "Big deal" });
		expect(inserts()).toEqual([]);
		expect(createRequests.value).toEqual([]);
	});

	it("carries a value changed away from its default", async () => {
		const { root } = await open("Lead");

		await type(root, "status", "Closed");
		await click(root, "Edit full form");

		expect(router.currentRoute.value.query).toEqual({ status: "Closed" });
	});
});

describe("defaults", () => {
	it("fill the empty fields when they arrive, and leave what the person typed", async () => {
		let answerDefaults!: () => void;
		server.newDoc = () =>
			new Promise((resolve) => {
				answerDefaults = () => resolve({ doctype: "Lead", name: "new-lead-1", title: "Untitled", status: "Open", source: "Web" });
			});
		const { root } = await open("Lead");
		expect(input(root, "status").value).toBe("");

		await type(root, "title", "Big deal");
		answerDefaults();
		await settle();

		expect(input(root, "title").value).toBe("Big deal");
		expect(input(root, "status").value).toBe("Open");
		expect(input(root, "source").value).toBe("Web");
	});

	it("do not overwrite the caller's values", async () => {
		server.newDoc = async () => ({ doctype: "Lead", status: "Open", source: "Web" });
		const { root } = await open("Lead", { status: "Closed" });

		expect(input(root, "status").value).toBe("Closed");
		expect(input(root, "source").value).toBe("Web");
	});
});

describe("closing and failures", () => {
	it("resolves null when the person closes the dialog, and sends nothing", async () => {
		const { root, answer } = await open("Lead");
		await click(root, "Close");

		expect(answer).toEqual({ settled: true, doc: null });
		expect(createRequests.value).toHaveLength(0);
		expect(inserts()).toEqual([]);
	});

	it("shows the error and refuses to save when the layout read fails", async () => {
		server.layoutsFail = true;
		const { root, answer } = await open("Lead", { title: "Prefilled" });

		expect(root.querySelector("[data-dialog]")).not.toBeNull();
		expect(root.querySelector(".error")!.textContent).toContain("Layouts are down");
		expect(button(root, "Save")!.disabled).toBe(true);
		root.querySelector("[data-dialog] div")!.dispatchEvent(
			new KeyboardEvent("keydown", { key: "Enter", ctrlKey: true, bubbles: true })
		);
		await settle();
		expect(inserts()).toEqual([]);
		expect(answer.settled).toBe(false);
	});

	it("shows the server's message when the defaults read fails, and still saves", async () => {
		server.newDocFails = true;
		const { root, answer } = await open("Lead");

		expect(root.querySelector(".error")!.textContent).toContain("No create right");
		await type(root, "title", "Typed");
		await click(root, "Save");
		expect(inserts()).toHaveLength(1);
		expect(answer.settled).toBe(true);
	});
});

describe("while the insert runs", () => {
	it("cannot be closed, and answers with the saved record", async () => {
		let answerInsert!: () => void;
		server.insert = (body) =>
			new Promise((resolve) => {
				answerInsert = () => resolve(json({ data: { ...body, name: "LEAD-0002", doctype: "Lead" } }));
			});
		const { root, answer } = await open("Lead");
		await type(root, "title", "Slow");
		await click(root, "Save");

		expect(button(root, "Close")).toBeUndefined();
		answerInsert();
		await settle();
		expect(answer.settled).toBe(true);
		expect(answer.doc).toMatchObject({ name: "LEAD-0002" });
	});
});

describe("the row and late defaults", () => {
	const ROW = {
		name: 1,
		condition: "eval:doc.status === 'Open'",
		layout: [{ sections: [{ columns: [{ fields: ["title", "company"] }] }] }],
	};

	function lateDefaults() {
		let answerDefaults!: () => void;
		server.layouts = { ...server.layouts, layouts: [ROW] };
		server.newDoc = () =>
			new Promise((resolve) => {
				answerDefaults = () => resolve({ doctype: "Lead", status: "Open" });
			});
		return () => answerDefaults();
	}

	function shownFields(root: HTMLElement) {
		return [...root.querySelectorAll("input")].map((field) => field.name);
	}

	it("switches to the row the defaults match while the person has typed nothing", async () => {
		const answerDefaults = lateDefaults();
		const { root } = await open("Lead");
		expect(shownFields(root)).toEqual(["title", "status", "source"]);

		answerDefaults();
		await settle();
		expect(shownFields(root)).toEqual(["title", "company"]);
	});

	it("keeps the row once the person has typed", async () => {
		const answerDefaults = lateDefaults();
		const { root } = await open("Lead");
		await type(root, "title", "Typing");

		answerDefaults();
		await settle();
		expect(shownFields(root)).toEqual(["title", "status", "source"]);
	});
});
