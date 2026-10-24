// "Create" in a Link or Table MultiSelect field's dropdown: when it shows, what the new record starts
// with, what the field takes after a save, and Create dialogs stacked above other dialogs. Fetch is faked.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, watch, type App, type Component } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

// A passthrough Dialog that ends its leave at once, so the test reads the forms, not reka-ui.
vi.mock("frappe-ui", async (importOriginal) => ({
	...((await importOriginal()) as Record<string, unknown>),
	Dialog: defineComponent({
		props: { open: { type: Boolean, default: true }, title: String },
		emits: ["update:open", "after-leave"],
		setup(props, { slots, emit }) {
			watch(
				() => props.open,
				(open) => !open && emit("after-leave")
			);
			return () =>
				props.open
					? h("section", { "data-dialog": props.title }, [
							h("button", { onClick: () => emit("update:open", false) }, "Close"),
							h("div", slots.default?.()),
							h("div", slots.actions?.()),
						])
					: null;
		},
	}),
}));

// The real FormLayout is exercised in Chrome; this one draws the real Link field and an input otherwise.
vi.mock("@framework/ui/components/FormLayout", () => ({
	FormLayout: defineComponent({
		props: { layout: { type: Array, required: true }, doc: { type: Object, required: true } },
		emits: ["update:doc"],
		setup(props, { emit }) {
			const fields = () =>
				(props.layout as any[]).flatMap((tab) =>
					tab.sections.flatMap((section: any) => section.columns.flatMap((column: any) => column.fields))
				);
			const update = (fieldname: string, value: unknown) =>
				emit("update:doc", { ...props.doc, [fieldname]: value });
			return () =>
				h(
					"form",
					fields().map((field: any) =>
						field.fieldtype === "Link"
							? h("div", { "data-field": field.fieldname }, [
									h(LinkField, {
										field,
										modelValue: props.doc[field.fieldname],
										"onUpdate:modelValue": (value: unknown) => update(field.fieldname, value),
									}),
								])
							: h("input", {
									name: field.fieldname,
									value: props.doc[field.fieldname] ?? "",
									onInput: (event: Event) => update(field.fieldname, (event.target as HTMLInputElement).value),
								})
					)
				);
		},
	}),
}));

import type { Session } from "@framework/ui/api";
import { clearDataCache } from "@framework/ui/cache";
import DynamicLinkField from "@framework/ui/components/Fields/DynamicLinkField.vue";
import LinkField from "@framework/ui/components/Fields/LinkField.vue";
import TableMultiSelectField from "@framework/ui/components/Fields/TableMultiSelectField.vue";
import Filter from "@framework/ui/components/Filter/Filter.vue";
import QuickFilterInputs from "@framework/ui/components/QuickFilter/QuickFilterInputs.vue";
import { CreateRecordKey, DocKey } from "@framework/ui/components/Fields/types";
import type { FieldMeta } from "@framework/ui/components/Fields/types";
import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetSession, setSession } from "@framework/ui/composables/useSession";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { useCreateRight } from "@/createRight";
import { registerShell } from "@/router/routeFor";
import { resetFormLayouts } from "@/recordPage";
import { createPageDialogs } from "@/recordPage/dialog";
import { closeCreates, createDialog, createRequests, openCreate, registerCreateDialog } from "@/shell/create";
import PageDialogs from "@/pages/record/dialogs/PageDialogs.vue";
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
	doctypes: { Customer: ["customer", "selling"], Territory: ["territory", "selling"] },
	modules: { selling: "Selling" },
});

const CREATE = [{ role: "Sales User", permlevel: 0, read: 1, write: 1, create: 1 }];

type Meta = Record<string, any>;

function customerMeta(overrides: Meta = {}): Meta {
	return {
		name: "Customer",
		autoname: "naming_series:",
		fields: [
			{ fieldname: "customer_name", fieldtype: "Data", label: "Customer Name" },
			{ fieldname: "status", fieldtype: "Select", label: "Status", options: "Active\nBlocked" },
			{ fieldname: "territory", fieldtype: "Link", label: "Territory", options: "Territory" },
			{ fieldname: "is_frozen", fieldtype: "Check", label: "Is Frozen" },
			{ fieldname: "contacts", fieldtype: "Table", label: "Contacts", options: "Customer Contact" },
		],
		permissions: CREATE,
		...overrides,
	};
}

const territoryMeta: Meta = {
	name: "Territory",
	autoname: "Prompt",
	fields: [{ fieldname: "parent_territory", fieldtype: "Data", label: "Parent" }],
	permissions: CREATE,
};

let metas: Record<string, Meta>;
let saved: Record<string, any>;
const fetchMock = vi.fn<typeof fetch>();
const apps: App[] = [];

function json(body: unknown, status = 200) {
	return new Response(JSON.stringify(body), { status });
}

function requests(match: (path: string, init?: RequestInit) => boolean) {
	return fetchMock.mock.calls
		.map(([url, init]) => ({ url: new URL(String(url), "http://x"), init }))
		.filter(({ url, init }) => match(url.pathname, init));
}

function inserts() {
	return requests((path, init) => init?.method === "POST").map(({ url, init }) => ({
		doctype: decodeURIComponent(url.pathname.split("/").pop()!),
		body: JSON.parse(String(init!.body)),
	}));
}

const metaReads = () => requests((path) => path.endsWith("/meta")).length;
const searches = () => requests((path) => path.endsWith("/search"));

beforeEach(() => {
	resetDoctypeMeta();
	resetFormLayouts();
	clearDataCache();
	setSession(SESSION);
	registerCreateDialog(CreateDialog);
	closeCreates();
	metas = { Customer: customerMeta(), Territory: territoryMeta };
	saved = {};
	fetchMock.mockReset().mockImplementation(async (url, init) => {
		const address = new URL(String(url), "http://x");
		const path = address.pathname;
		const doctype = decodeURIComponent(path.split("/")[4] ?? "");
		if (path.endsWith("/meta")) return json({ data: metas[doctype] ?? null });
		if (path.endsWith("/search")) return json({ data: [] });
		if (path === LAYOUTS) {
			const meta = metas[address.searchParams.get("dt")!];
			const fieldnames = meta.fields.filter((field: any) => field.fieldtype !== "Table").map((field: any) => field.fieldname);
			return json({ data: { layouts: [], fallback: [{ sections: [{ columns: [{ fields: fieldnames }] }] }], dialog: true } });
		}
		if (path === NEW_DOC) return json({ data: {} });
		if (init?.method === "POST") {
			const body = JSON.parse(String(init.body));
			const doc = { ...body, ...saved[doctype], doctype };
			return json({ data: doc });
		}
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
	for (let turn = 0; turn < 6; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

/** The shell's Create host beside a page part, as `AppShell` draws them. */
const Host = defineComponent({
	props: { part: { type: Function, required: true } },
	setup(props) {
		return () => [
			h("main", (props.part as () => unknown)()),
			createRequests.value.map((request) => h(createDialog() as Component, { key: request.id, request })),
		];
	},
});

function mount(part: () => unknown, { create = true, readOnlyMode = false } = {}) {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [
			{ path: "/:doctype/new", name: "new-record", component: { render: () => null } },
			{ path: "/:any(.*)", component: { render: () => null } },
		],
	});
	const boot = { app: "erp", shell_base: "/apps/erp", prefixes: { erp: { app: "erp", modular: false } }, read_only_mode: readOnlyMode };
	registerShell({ boot: boot as unknown as Boot, addresses, router });
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(Host, { part });
	app.use(router);
	app.provide("boot", boot);
	if (create) app.provide(CreateRecordKey, { open: openCreate, useRight: useCreateRight });
	app.mount(root);
	apps.push(app);
	return { root, router };
}

/** A Link field to Customer on a page, with its value in a ref and every change it fires. */
function linkField(field: Partial<FieldMeta> = {}, options: Parameters<typeof mount>[1] = {}) {
	const value = ref<string | null>(null);
	const changes: unknown[] = [];
	const meta: FieldMeta = { fieldname: "customer", fieldtype: "Link", label: "Customer", options: "Customer", ...field };
	const { root, router } = mount(
		() =>
			h("div", { "data-field": "customer" }, [
				h(LinkField, {
					field: meta,
					modelValue: value.value,
					"onUpdate:modelValue": (next: string | null) => (value.value = next),
					onChange: (next: unknown) => changes.push(next),
				}),
			]),
		options
	);
	return { root, router, value, changes };
}

function within(fieldname: string, scope: ParentNode = document) {
	return scope.querySelector(`[data-field='${fieldname}']`)!;
}

/** Opens the field's dropdown with the typed text, as a person typing does. */
async function search(fieldname: string, text = "", scope: ParentNode = document) {
	const input = within(fieldname, scope).querySelector<HTMLInputElement>("input")!;
	if (text) {
		input.value = text;
		input.dispatchEvent(new Event("input", { bubbles: true }));
	} else {
		within(fieldname, scope).querySelector<HTMLButtonElement>("[data-slot=chevron]")!.click();
	}
	await new Promise((resolve) => setTimeout(resolve, 350));
	await settle();
}

function rows(): string[] {
	return [...document.querySelectorAll("[role=option]")].map((row) => row.textContent!.trim());
}

async function chooseCreate() {
	const row = [...document.querySelectorAll<HTMLElement>("[role=option]")].at(-1)!;
	row.click();
	await settle();
}

function dialogs(): string[] {
	return [...document.querySelectorAll("[data-dialog]")].map((dialog) => dialog.getAttribute("data-dialog")!);
}

function dialog(title: string) {
	return document.querySelector<HTMLElement>(`[data-dialog='${title}']`)!;
}

async function press(scope: HTMLElement, label: string) {
	const button = [...scope.querySelectorAll("button")].find((element) => element.textContent?.trim() === label)!;
	button.focus();
	button.click();
	await settle();
}

async function type(scope: HTMLElement, fieldname: string, text: string) {
	const input = scope.querySelector<HTMLInputElement>(`input[name='${fieldname}']`)!;
	input.value = text;
	input.dispatchEvent(new Event("input"));
	await settle();
}

describe("when the option shows", () => {
	it("is the last row once the linked meta loads on the first open, and reads no meta before", async () => {
		linkField();
		await settle();
		expect(metaReads()).toBe(0);

		await search("customer");

		expect(metaReads()).toBe(1);
		expect(rows().at(-1)).toBe("Create new Customer");
	});

	it("is not offered where the host gives no Create, and the meta is never read", async () => {
		linkField({}, { create: false });

		await search("customer", "Acme");

		expect(rows()).not.toContain('Create "Acme"');
		expect(rows().some((row) => row.startsWith("Create"))).toBe(false);
		expect(metaReads()).toBe(0);
	});

	it.each([
		["the person holds no create right", { permissions: [{ role: "Sales User", permlevel: 0, read: 1 }] }],
		["the doctype is in_create", { in_create: 1 }],
		["the doctype is single", { issingle: 1 }],
		["the doctype is a child table", { istable: 1 }],
	])("is not offered when %s", async (_case, overrides) => {
		metas.Customer = customerMeta(overrides);
		linkField();

		await search("customer", "Acme");

		expect(rows().some((row) => row.startsWith("Create"))).toBe(false);
	});

	it("is not offered in a list filter's value input", async () => {
		vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
		mount(() =>
			h("div", { "data-field": "customer" }, [
				h(QuickFilterInputs, { fields: [{ fieldname: "customer", fieldtype: "Link", label: "Customer", options: "Customer" }] }),
			])
		);

		await search("customer", "Acme");

		expect(rows().some((row) => row.startsWith("Create"))).toBe(false);
		expect(metaReads()).toBe(0);
	});

	it("is not offered in the filter popover's value input", async () => {
		const territory = { fieldname: "territory", fieldtype: "Link", label: "Territory", options: "Territory" };
		mount(() => h(Filter, { doctype: "Customer", modelValue: [{ fieldname: "territory", operator: "equals", value: "", field: territory }] }));
		await settle();
		[...document.querySelectorAll("button")].find((button) => button.textContent?.trim().startsWith("Filter"))!.click();
		await settle();

		const input = document.querySelector<HTMLInputElement>("input[placeholder='Select a Value']")!;
		input.value = "North";
		input.dispatchEvent(new Event("input", { bubbles: true }));
		await new Promise((resolve) => setTimeout(resolve, 350));
		await settle();

		expect(searches().some(({ url }) => url.pathname.includes("Territory") && url.searchParams.get("txt") === "North")).toBe(true);
		expect(rows().some((row) => row.startsWith("Create"))).toBe(false);
		expect(requests((path) => path.includes("Territory/meta"))).toEqual([]);
	});

	it("is not offered in read-only mode", async () => {
		linkField({}, { readOnlyMode: true });

		await search("customer", "Acme");

		expect(rows().some((row) => row.startsWith("Create"))).toBe(false);
	});
});

describe("what the new record starts with", () => {
	it.each([
		["a field: naming rule, in any letter case, fills that field", { autoname: "Field:customer_name" }, { customer_name: "Acme" }],
		["a prompt name, in any letter case, fills the name field", { autoname: "PROMPT" }, { __newname: "Acme" }],
		["otherwise the title field", { title_field: "customer_name" }, { customer_name: "Acme" }],
	])("%s", async (_case, overrides, values) => {
		metas.Customer = customerMeta(overrides);
		linkField();

		await search("customer", "Acme");
		expect(rows().at(-1)).toBe('Create "Acme"');
		await chooseCreate();

		expect(createRequests.value.map((request) => request.values)).toEqual([values]);
	});

	it("drops the typed text when nothing names the record by it, and says Create new", async () => {
		linkField();

		await search("customer", "Acme");
		expect(rows().at(-1)).toBe("Create new Customer");
		await chooseCreate();

		expect(createRequests.value.map((request) => request.values)).toEqual([{}]);
	});

	it("prefills the field's equality filters on the doctype's own fields, under the typed text", async () => {
		metas.Customer = customerMeta({ title_field: "customer_name" });
		linkField({
			filters: {
				status: "Active",
				territory: ["=", "North"],
				customer_name: "Filtered",
				is_frozen: true,
				contacts: "C-1",
				unknown: "x",
				disabled: ["!=", 1],
			},
		});

		await search("customer", "Acme");
		await chooseCreate();

		expect(createRequests.value[0].values).toEqual({
			status: "Active",
			territory: "North",
			is_frozen: 1,
			customer_name: "Acme",
		});
	});
});

describe("after the Create call", () => {
	it("takes the saved name, fires the field's change, shows the title and searches past the browser cache", async () => {
		metas.Customer = customerMeta({ title_field: "customer_name", show_title_field_in_link: 1 });
		saved.Customer = { name: "CUST-0001" };
		const { value, changes } = linkField();

		await search("customer", "Acme");
		await chooseCreate();
		expect(dialogs()).toEqual(["New Customer"]);
		await press(dialog("New Customer"), "Save");

		expect(inserts()).toEqual([{ doctype: "Customer", body: { customer_name: "Acme", status: null, territory: null, is_frozen: null } }]);
		expect(value.value).toBe("CUST-0001");
		expect(changes).toEqual(["CUST-0001"]);
		expect(within("customer").querySelector("input")!.value).toBe("Acme");
		const fresh = searches().filter(({ init }) => init?.cache === "reload");
		expect(fresh.map(({ url }) => url.searchParams.get("txt"))).toEqual(["Acme"]);
		expect(document.activeElement).toBe(within("customer").querySelector("input"));
	});

	it("leaves the field as it was when the dialog is dismissed, with focus back in it", async () => {
		const { value, changes } = linkField();

		await search("customer", "Acme");
		await chooseCreate();
		await press(dialog("New Customer"), "Close");

		expect(dialogs()).toEqual([]);
		expect(value.value).toBeNull();
		expect(changes).toEqual([]);
		expect(inserts()).toEqual([]);
		expect(document.activeElement).toBe(within("customer").querySelector("input"));
	});

	it("leaves the field as it was when the person goes to the full form", async () => {
		metas.Customer = customerMeta({ title_field: "customer_name" });
		const { value, router } = linkField();

		await search("customer", "Acme");
		await chooseCreate();
		await press(dialog("New Customer"), "Edit full form");

		expect(router.currentRoute.value.fullPath).toBe("/customer/new?customer_name=Acme");
		expect(value.value).toBeNull();
		expect(inserts()).toEqual([]);
	});
});

describe("a Dynamic Link field", () => {
	function dynamicLinkField() {
		const doc = ref<Record<string, any>>({ reference_doctype: "Customer", reference_name: null });
		const field: FieldMeta = { fieldname: "reference_name", fieldtype: "Dynamic Link", label: "Reference", options: "reference_doctype" };
		const Part = defineComponent({
			setup() {
				return () =>
					h("div", { "data-field": "reference_name" }, [
						h(DynamicLinkField, {
							field,
							modelValue: doc.value.reference_name,
							"onUpdate:modelValue": (next: string | null) => (doc.value = { ...doc.value, reference_name: next }),
						}),
					]);
			},
			provide: { [DocKey as symbol]: doc },
		});
		mount(() => h(Part));
		return doc;
	}

	it("creates a record of the doctype its sibling names and takes its name", async () => {
		metas.Customer = customerMeta({ autoname: "field:customer_name" });
		saved.Customer = { name: "Acme" };
		const doc = dynamicLinkField();

		await search("reference_name", "Acme");
		expect(rows().at(-1)).toBe('Create "Acme"');
		await chooseCreate();
		await press(dialog("New Customer"), "Save");

		expect(inserts()[0]).toMatchObject({ doctype: "Customer", body: { customer_name: "Acme" } });
		expect(doc.value.reference_name).toBe("Acme");
	});

	it("drops the saved record's title once its sibling names another doctype", async () => {
		metas.Customer = customerMeta({ title_field: "customer_name", show_title_field_in_link: 1 });
		saved.Customer = { name: "CUST-0001" };
		const doc = dynamicLinkField();
		await search("reference_name", "Acme");
		await chooseCreate();
		await press(dialog("New Customer"), "Save");
		const input = () => within("reference_name").querySelector("input")!.value;
		expect(input()).toBe("Acme");

		doc.value = { ...doc.value, reference_doctype: "Territory" };
		await settle();

		expect(doc.value.reference_name).toBe("CUST-0001");
		expect(input()).not.toBe("Acme");
	});

	it("does not take the name when its sibling moved to another doctype during the save", async () => {
		saved.Customer = { name: "CUST-0001" };
		const doc = dynamicLinkField();

		await search("reference_name", "Acme");
		await chooseCreate();
		doc.value = { ...doc.value, reference_doctype: "Territory" };
		await settle();
		await press(dialog("New Customer"), "Save");

		expect(inserts()).toHaveLength(1);
		expect(doc.value.reference_name).toBeNull();
	});
});

describe("stacking", () => {
	it("opens a Create dialog above a Create dialog, and a save fills the field in the dialog below", async () => {
		saved.Territory = { name: "North" };
		linkField();

		await search("customer");
		await chooseCreate();
		const customer = dialog("New Customer");
		await search("territory", "North", customer);
		expect(rows().at(-1)).toBe('Create "North"');
		await chooseCreate();

		expect(dialogs()).toEqual(["New Customer", "New Territory"]);
		await press(dialog("New Territory"), "Save");

		expect(inserts()).toEqual([{ doctype: "Territory", body: { __newname: "North", parent_territory: null } }]);
		expect(dialogs()).toEqual(["New Customer"]);
		await type(customer, "customer_name", "Acme");
		await press(customer, "Save");
		expect(inserts()[1]).toEqual({ doctype: "Customer", body: { customer_name: "Acme", status: null, territory: "North", is_frozen: null } });
	});

	it("closes only the top dialog on Close, and every dialog on a route change", async () => {
		linkField();
		await search("customer");
		await chooseCreate();
		await search("territory", "", dialog("New Customer"));
		await chooseCreate();
		expect(dialogs()).toEqual(["New Customer", "New Territory"]);

		await press(dialog("New Territory"), "Close");
		expect(dialogs()).toEqual(["New Customer"]);

		await search("territory", "", dialog("New Customer"));
		await chooseCreate();
		expect(dialogs()).toEqual(["New Customer", "New Territory"]);
		closeCreates();
		await settle();
		expect(dialogs()).toEqual([]);
	});

	it("opens a Create dialog above a page.dialog.form, and a save fills its field", async () => {
		saved.Customer = { name: "CUST-0001" };
		let answer: unknown;
		const pageDialogs = createPageDialogs({ isReplaying: () => false, hold: async (work) => work() });
		mount(() => h(PageDialogs, { controller: { dialogs: pageDialogs.entries } }));
		void pageDialogs.api
			.form({
				title: "Pick a customer",
				fields: [{ fieldname: "customer", fieldtype: "Link", label: "Customer", options: "Customer" }],
			})
			.then((result) => (answer = result));
		await settle();

		await search("customer", "", dialog("Pick a customer"));
		await chooseCreate();
		expect(dialogs()).toEqual(["Pick a customer", "New Customer"]);
		await type(dialog("New Customer"), "customer_name", "Acme");
		await press(dialog("New Customer"), "Save");

		expect(dialogs()).toEqual(["Pick a customer"]);
		await press(dialog("Pick a customer"), "Submit");
		expect(answer).toEqual({ customer: "CUST-0001" });
	});
});

describe("a Table MultiSelect field", () => {
	const childFields = [{ fieldname: "customer", fieldtype: "Link", label: "Customer", options: "Customer" }] as FieldMeta[];

	/** A Table MultiSelect of Customer rows on a page, with its rows in a ref and every change it fires. */
	function tableMultiSelectField(rows: Record<string, any>[] = [], field: Partial<FieldMeta> = {}, options: Parameters<typeof mount>[1] = {}) {
		const value = ref(rows);
		const changes: unknown[] = [];
		const meta: FieldMeta = { fieldname: "customers", fieldtype: "Table MultiSelect", label: "Customers", options: "Customer Item", childFields, ...field };
		mount(
			() =>
				h("div", { "data-field": "customers" }, [
					h(TableMultiSelectField, {
						field: meta,
						modelValue: value.value,
						"onUpdate:modelValue": (next: Record<string, any>[]) => (value.value = next),
						onChange: (next: unknown) => changes.push(next),
					}),
				]),
			options
		);
		const picked = () => value.value.map((row) => row.customer);
		return { value, picked, changes };
	}

	const trigger = () => within("customers").querySelector<HTMLButtonElement>("button")!;
	const footer = () => document.querySelector<HTMLElement>("[data-slot=footer]");
	const footerButtons = () => [...(footer()?.querySelectorAll("button") ?? [])].map((button) => button.textContent!.trim());
	const chips = () => [...trigger().querySelectorAll("span.h-7")].map((chip) => chip.textContent!.trim());

	/** Opens the dropdown and types the text into its search, as a person does. */
	async function pick(text = "") {
		trigger().click();
		await settle();
		if (!text) return;
		const input = document.querySelector<HTMLInputElement>("[data-slot=search] input")!;
		input.value = text;
		input.dispatchEvent(new Event("input", { bubbles: true }));
		await new Promise((resolve) => setTimeout(resolve, 350));
		await settle();
	}

	async function chooseFooterCreate() {
		const button = [...footer()!.querySelectorAll<HTMLButtonElement>("button")].find((element) => element.textContent!.trim().startsWith("Create"))!;
		button.click();
		await settle();
	}

	it("offers Create in the footer with no typed text, once the linked meta loads on the first open", async () => {
		tableMultiSelectField();
		await settle();
		expect(metaReads()).toBe(0);

		await pick();

		expect(requests((path) => path.includes("Customer/meta"))).toHaveLength(1);
		expect(footerButtons()).toEqual(["Create new Customer"]);
	});

	it("labels Create with the typed text when it names the record", async () => {
		metas.Customer = customerMeta({ autoname: "field:customer_name" });
		tableMultiSelectField();

		await pick("Acme");

		expect(footerButtons()).toEqual(['Create "Acme"']);
	});

	it.each<[string, Partial<FieldMeta>, Parameters<typeof mount>[1], Meta]>([
		["the host gives no Create", {}, { create: false }, {}],
		["the field is read-only", { readOnly: true }, {}, {}],
		["the person holds no create right", {}, {}, { permissions: [{ role: "Sales User", permlevel: 0, read: 1 }] }],
	])("is not offered when %s", async (_case, field, options, overrides) => {
		metas.Customer = customerMeta(overrides);
		tableMultiSelectField([], field, options);

		await pick();

		expect(footerButtons().some((label) => label.startsWith("Create"))).toBe(false);
	});

	it("prefills the typed text and the field's equality filters, and closes the dropdown", async () => {
		metas.Customer = customerMeta({ title_field: "customer_name" });
		tableMultiSelectField([], { filters: { territory: "North", disabled: ["!=", 1] } });

		await pick("Acme");
		await chooseFooterCreate();

		expect(createRequests.value.map((request) => request.values)).toEqual([{ territory: "North", customer_name: "Acme" }]);
		expect(footer()).toBeNull();
	});

	it("adds the saved name as a row, fires the change, shows its title and searches past the browser cache", async () => {
		metas.Customer = customerMeta({ title_field: "customer_name", show_title_field_in_link: 1 });
		saved.Customer = { name: "CUST-0002" };
		const { picked, changes } = tableMultiSelectField([{ customer: "CUST-0001" }]);

		await pick("Acme");
		await chooseFooterCreate();
		await press(dialog("New Customer"), "Save");

		expect(picked()).toEqual(["CUST-0001", "CUST-0002"]);
		expect(changes).toHaveLength(1);
		expect(chips()).toEqual(["CUST-0001", "Acme"]);
		const fresh = searches().filter(({ init }) => init?.cache === "reload");
		expect(fresh.map(({ url }) => url.searchParams.get("txt"))).toEqual(["Acme"]);
		expect(document.activeElement).toBe(trigger());
		await pick();
		expect(document.querySelector<HTMLInputElement>("[data-slot=search] input")!.value).toBe("");
	});

	it("keeps the title of each record it created, not only the last", async () => {
		metas.Customer = customerMeta({ title_field: "customer_name", show_title_field_in_link: 1 });
		const { picked } = tableMultiSelectField();

		for (const [name, title] of [["CUST-0001", "Acme"], ["CUST-0002", "Beta"]]) {
			saved.Customer = { name };
			await pick(title);
			await chooseFooterCreate();
			await press(dialog("New Customer"), "Save");
		}

		expect(picked()).toEqual(["CUST-0001", "CUST-0002"]);
		expect(chips()).toEqual(["Acme", "Beta"]);
	});

	it("adds no second row when the saved name is already selected", async () => {
		saved.Customer = { name: "CUST-0001" };
		const { picked, changes } = tableMultiSelectField([{ customer: "CUST-0001" }]);

		await pick();
		await chooseFooterCreate();
		await press(dialog("New Customer"), "Save");

		expect(picked()).toEqual(["CUST-0001"]);
		expect(changes).toEqual([]);
	});

	it("leaves the rows as they were when the dialog is dismissed, with focus back on the trigger", async () => {
		const { value, changes } = tableMultiSelectField([{ customer: "CUST-0001" }]);
		const before = value.value;

		await pick("Acme");
		await chooseFooterCreate();
		await press(dialog("New Customer"), "Close");

		expect(dialogs()).toEqual([]);
		expect(value.value).toBe(before);
		expect(changes).toEqual([]);
		expect(inserts()).toEqual([]);
		expect(document.activeElement).toBe(trigger());
	});

	it("clears every row from the footer's Clear All", async () => {
		const { picked } = tableMultiSelectField([{ customer: "CUST-0001" }]);

		await pick();
		const clear = [...footer()!.querySelectorAll<HTMLButtonElement>("button")].find((button) => button.textContent!.trim() === "Clear All")!;
		clear.click();
		await settle();

		expect(picked()).toEqual([]);
	});
});
