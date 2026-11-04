// The list draws each column's cell as the record's read-only field shows the value, and a Phone or
// Email column's cells (a Phone field, or a Data field whose options say Phone or Email) with the field actions,
// a Link or Dynamic Link value as a link to the record it names, and a web address with a link that opens it.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

const metaFields = [
	{ fieldname: "mobile_no", fieldtype: "Phone" },
	{ fieldname: "phone", fieldtype: "Data", options: "Phone" },
	{ fieldname: "status", fieldtype: "Data" },
	{ fieldname: "email_id", fieldtype: "Data", options: "Email" },
	{ fieldname: "website", fieldtype: "Data", options: "URL" },
	{ fieldname: "homepage", fieldtype: "Data", options: "URL" },
	{ fieldname: "currency", fieldtype: "Link", options: "Currency" },
	{ fieldname: "amount", fieldtype: "Currency", options: "currency" },
	{ fieldname: "fee", fieldtype: "Currency", options: "Company:company:default_currency" },
	{ fieldname: "secret", fieldtype: "Password" },
	{ fieldname: "ratio", fieldtype: "Float", precision: "2" },
	{ fieldname: "done", fieldtype: "Percent" },
	{ fieldname: "taken", fieldtype: "Duration" },
	{ fieldname: "at", fieldtype: "Time" },
	{ fieldname: "creation", fieldtype: "Datetime" },
	{ fieldname: "modified", fieldtype: "Datetime" },
	{ fieldname: "closed_on", fieldtype: "Datetime" },
	{ fieldname: "notes", fieldtype: "Text Editor" },
	{ fieldname: "file", fieldtype: "Attach" },
	{ fieldname: "script", fieldtype: "Code" },
	{ fieldname: "color", fieldtype: "Color" },
	{ fieldname: "active", fieldtype: "Check" },
	{ fieldname: "score", fieldtype: "Rating" },
	{ fieldname: "deal", fieldtype: "Link", options: "CRM Deal" },
	{ fieldname: "agent", fieldtype: "Link", options: "User" },
	{ fieldname: "lead_owner", fieldtype: "Link", options: "User" },
	{ fieldname: "ref_doctype", fieldtype: "Link", options: "DocType" },
	{ fieldname: "reference", fieldtype: "Dynamic Link", options: "ref_doctype" },
	{ fieldname: "other_doctype", fieldtype: "Link", options: "DocType" },
	{ fieldname: "other", fieldtype: "Dynamic Link", options: "other_doctype" },
];
const columns = [
	...metaFields.map(({ fieldname }) => ({ fieldname, label: fieldname })),
	{ fieldname: "_extra", label: "Extra" },
];
const row = {
	name: "L1",
	mobile_no: "555",
	phone: "555",
	status: "Open",
	email_id: "lead@example.com",
	website: "https://example.com/about",
	homepage: "example.com",
	currency: "USD",
	amount: 1234567.5,
	fee: 10,
	fee__currency: "EUR",
	secret: "*****",
	ratio: 12345.6789,
	done: 42.5,
	taken: 93784,
	at: "9:15:30",
	creation: "2026-11-01 10:00:00.604123",
	modified: "2026-11-04 10:00:00.604123",
	closed_on: "2026-11-04 00:44:09.604123",
	notes: "<p>Hello <strong>bold</strong> world</p>",
	file: "/files/report.pdf",
	script: "def f():\n    return 1",
	color: "#E03636",
	active: 1,
	score: 0.6,
	deal: "D-1",
	agent: "ann@example.com",
	agent__mark: "/files/ann.png",
	lead_owner: "bob@example.com",
	ref_doctype: "User",
	reference: "ann@example.com",
	other_doctype: "",
	other: "orphan",
	_extra: "as sent",
};

const original = { ...row };

vi.mock("@/list/useListView", () => ({
	useListView: () => ({
		columns: ref(columns),
		rows: ref([row]),
		selection: ref([]),
		pageSize: ref(20),
		rowsKey: () => "",
		loading: ref(false),
		error: ref(null),
		rowCount: ref(1),
		totalCount: ref(1),
		totalCapped: ref(false),
		totalUnknown: ref(false),
		hasCounts: ref(true),
		hasNextPage: ref(false),
		rowActions: [],
		fieldOf: (fieldname: string) => metaFields.find((field) => field.fieldname === fieldname),
		markOf: (fieldname: string) =>
			fieldname === "agent" ? { source: { kind: "image", field: "user_image" }, key: "agent__mark" } : undefined,
		currencyOf: (fieldname: string) =>
			({ amount: { key: "currency" }, fee: { key: "fee__currency" } })[fieldname],
		linkTitles: ref({ "CRM Deal::D-1": "Acme", "User::ann@example.com": "Ann Lee" }),
		columnsCustomized: ref(false),
		rowLink: () => ({}),
	}),
}));
vi.mock("@framework/ui/experimental/List", async () => {
	const { defineComponent, h } = await import("vue");
	const stub = () => defineComponent({ setup: () => () => null });
	return {
		ListBulkBar: stub(),
		ListFooter: stub(),
		// Draws the `cell` slot once per column, the way the table does per row.
		List: defineComponent({
			props: ["columns"],
			setup:
				(props, { slots }) =>
				() =>
					h(
						"div",
						props.columns.map((column: { fieldname: string }) => {
							const value = String(row[column.fieldname as keyof typeof row]);
							return h("div", { "data-column": column.fieldname }, slots.cell?.({ row, column, value }));
						})
					),
		}),
	};
});
// The real tooltip draws its text only on hover; this one leaves it on the trigger.
vi.mock("frappe-ui", async (original) => ({
	...(await original<typeof import("frappe-ui")>()),
	Tooltip: defineComponent({
		props: ["text"],
		setup: (props, { slots }) => () => h("span", { "data-tooltip": props.text }, slots.default?.()),
	}),
}));
vi.mock("@/shell/PageState.vue", () => ({ default: defineComponent({ render: () => null }) }));

import { FieldActionsKey, RecordLinkKey } from "@framework/ui/fields/types";
import { resetSession, setSession } from "@framework/ui/useSession";
import ListView from "../ListView.vue";

const mounted: ReturnType<typeof createApp>[] = [];
const openRecord = vi.fn();

function mount(): HTMLElement {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const host = { controls: ref(null), onCreate: vi.fn(), acts: () => ({ drawn: () => null }) };
	const view = { doctype: "CRM Lead", filters: ref([]), sort: ref([]) };
	const app = createApp(
		defineComponent({ render: () => h(ListView, { view: view as never, host: host as never }) })
	);
	app.provide(FieldActionsKey, {
		for: (field, value, record) => [
			{ act: "a", label: `Call ${field.fieldname} ${value} ${JSON.stringify(record ?? null)}`, run: vi.fn() },
		],
	});
	app.provide(RecordLinkKey, {
		href: (doctype, name) => (doctype === "DocType" ? null : `/r/${doctype}/${name}`),
		open: openRecord,
	});
	app.mount(root);
	mounted.push(app);
	return root;
}

afterEach(() => {
	Object.assign(row, original);
	vi.unstubAllEnvs();
	vi.useRealTimers();
	resetSession();
	openRecord.mockClear();
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

describe("a list's cells", () => {
	it("draw the field actions in a Phone or Email cell and none in another column's", async () => {
		const root = mount();
		await nextTick();

		const labelIn = (column: string) =>
			root.querySelector(`[data-column='${column}'] [data-slot='field-action']`)?.getAttribute("aria-label");
		expect(labelIn("mobile_no")).toBe("Call mobile_no 555 null");
		expect(labelIn("phone")).toBe("Call phone 555 null");
		// An Email cell tells the host which row it sits on, and draws its button before the address.
		expect(labelIn("email_id")).toBe(
			'Call email_id lead@example.com {"doctype":"CRM Lead","name":"L1","surface":"list"}'
		);
		const cell = root.querySelector("[data-column='email_id'] > div")!;
		expect(cell.firstElementChild?.getAttribute("data-slot")).toBe("email-cell-actions");
		expect(labelIn("status")).toBeUndefined();
	});

	it("draw every other cell as the record's read-only field shows the value", async () => {
		const root = mount();
		await nextTick();

		const text = (column: string) => root.querySelector(`[data-column='${column}']`)?.textContent?.trim();
		expect(text("status")).toBe("Open");
		expect(text("amount")).toBe("$ 1,234,567.50");
		expect(text("fee")).toBe("€ 10.00");
		expect(text("secret")).toBe("••••••••");
		expect(text("ratio")).toBe("12,345.68");
		expect(text("done")).toBe("42.50%");
		expect(text("taken")).toBe("26h 3m 4s");
		expect(text("at")).toBe("09:15");
		expect(text("closed_on")).toBe("2026-11-04 00:44:09");
		expect(text("notes")).toBe("Hello bold world");
		expect(text("file")).toBe("/files/report.pdf");
		expect(text("script")).toBe("def f():\n    return 1");
		expect(text("color")).toBe("#E03636");
		expect(root.querySelector("[data-column='color'] [data-slot='swatch']")).not.toBeNull();
		expect(text("_extra")).toBe("as sent");
	});

	it("draw Last Modified and Created On as relative time, read on the site's clock, with the date on hover", async () => {
		// 10:00 in Asia/Kolkata is 04:30 UTC; a browser far from it would read the stamp hours off.
		vi.stubEnv("TZ", "America/Los_Angeles");
		vi.useFakeTimers({ toFake: ["Date"] });
		vi.setSystemTime(new Date("2026-11-04T04:33:00Z"));
		setSession({ user: {}, roles: [], lang: "en", timezone: "Asia/Kolkata", defaults: {} } as never);
		const root = mount();
		await nextTick();

		const cell = (column: string) => root.querySelector(`[data-column='${column}'] [data-tooltip]`);
		expect(cell("modified")?.textContent).toBe("3 minutes ago");
		expect(cell("modified")?.getAttribute("data-tooltip")).toBe("2026-11-04 10:00:00");
		expect(cell("creation")?.textContent).toBe("3 days ago");
		expect(cell("creation")?.getAttribute("data-tooltip")).toBe("2026-11-01 10:00:00");
		// Another Datetime field keeps its absolute value.
		expect(root.querySelector("[data-column='closed_on']")?.textContent?.trim()).toBe("2026-11-04 00:44:09");
		expect(cell("closed_on")).toBeNull();
	});

	it("keep the absolute value without a site zone, draw a bad or empty stamp as it is, and never read the future", async () => {
		vi.useFakeTimers({ toFake: ["Date"] });
		vi.setSystemTime(new Date("2026-11-04T04:33:00Z"));
		const cell = async (column: string) => {
			const root = mount();
			await nextTick();
			return root.querySelector(`[data-column='${column}']`)?.textContent?.trim();
		};
		expect(await cell("modified")).toBe("2026-11-04 10:00:00");

		setSession({ user: {}, roles: [], lang: "en", timezone: "Asia/Kolkata", defaults: {} } as never);
		Object.assign(row, { modified: "garbage", creation: "" });
		expect(await cell("modified")).toBe("garbage");
		expect(await cell("creation")).toBe("");
		// 10:05 in Asia/Kolkata is ahead of the browser's clock by two minutes.
		Object.assign(row, { modified: "2026-11-04 10:05:00" });
		expect(await cell("modified")).toBe("a few seconds ago");
	});

	it("draw a Link value as its target's title, a marked one too, and the name where none is held", async () => {
		const root = mount();
		await nextTick();

		const text = (column: string) => root.querySelector(`[data-column='${column}']`)?.textContent?.trim();
		expect(text("deal")).toBe("Acme");
		expect(text("agent")).toBe("Ann Lee");
		expect(root.querySelector("[data-column='agent'] img")?.getAttribute("alt")).toBe("Ann Lee");
		expect(text("lead_owner")).toBe("bob@example.com");
		// A Dynamic Link's title is never read, so a Link column's title for the same record is not borrowed.
		expect(text("reference")).toBe("ann@example.com");
	});

	it("draw a Link or Dynamic Link value as a link to its record, a marked one too", async () => {
		const root = mount();
		await nextTick();

		const anchor = (column: string) => root.querySelector<HTMLAnchorElement>(`[data-column='${column}'] a`);
		expect(anchor("deal")?.getAttribute("href")).toBe("/r/CRM Deal/D-1");
		expect(anchor("deal")?.textContent?.trim()).toBe("Acme");
		expect(anchor("agent")?.getAttribute("href")).toBe("/r/User/ann@example.com");
		expect(anchor("agent")?.textContent?.trim()).toBe("Ann Lee");
		// A Dynamic Link opens a record of the doctype its sibling field names.
		expect(anchor("reference")?.getAttribute("href")).toBe("/r/User/ann@example.com");
		// A doctype with no record page, or a Dynamic Link with no doctype, draws the text alone.
		expect(anchor("ref_doctype")).toBeNull();
		expect(anchor("other")).toBeNull();
		expect(root.querySelector("[data-column='other']")?.textContent?.trim()).toBe("orphan");
		expect(anchor("status")).toBeNull();
	});

	it("open the linked record on a plain click, not the row, and leave a modified click to the browser", async () => {
		const root = mount();
		await nextTick();
		const rowClicks = vi.fn();
		root.addEventListener("click", rowClicks);

		const deal = root.querySelector<HTMLAnchorElement>("[data-column='deal'] a")!;
		const plain = new MouseEvent("click", { bubbles: true, cancelable: true });
		deal.dispatchEvent(plain);
		expect(openRecord).toHaveBeenCalledWith("CRM Deal", "D-1");
		expect(plain.defaultPrevented).toBe(true);
		expect(rowClicks).not.toHaveBeenCalled();

		openRecord.mockClear();
		const modified = new MouseEvent("click", { bubbles: true, cancelable: true, ctrlKey: true });
		deal.dispatchEvent(modified);
		expect(openRecord).not.toHaveBeenCalled();
		expect(modified.defaultPrevented).toBe(false);
		expect(rowClicks).not.toHaveBeenCalled();
	});

	it("draw a web address with a link that opens it in a new tab, not the row", async () => {
		const root = mount();
		await nextTick();
		const rowClicks = vi.fn();
		root.addEventListener("click", rowClicks);

		const cell = root.querySelector("[data-column='website']")!;
		expect(cell.textContent?.trim()).toBe("https://example.com/about");
		const open = cell.querySelector<HTMLAnchorElement>("[data-slot='open-url']")!;
		expect(open.getAttribute("href")).toBe("https://example.com/about");
		expect(open.getAttribute("target")).toBe("_blank");
		expect(open.getAttribute("rel")).toBe("noopener noreferrer");
		expect(open.parentElement!.lastElementChild).toBe(open);
		const click = new MouseEvent("click", { bubbles: true, cancelable: true });
		open.dispatchEvent(click);
		expect(click.defaultPrevented).toBe(false);
		expect(rowClicks).not.toHaveBeenCalled();
		// Text that is not a web address draws alone, as the record's read-only field does.
		expect(root.querySelector("[data-column='homepage']")?.textContent?.trim()).toBe("example.com");
		expect(root.querySelector("[data-column='homepage'] a")).toBeNull();
	});

	it("draw a Check as a checkbox and a Rating as stars", async () => {
		const root = mount();
		await nextTick();

		const checkbox = root.querySelector<HTMLInputElement>("[data-column='active'] input[type='checkbox']");
		expect(checkbox?.checked).toBe(true);
		expect(checkbox?.disabled).toBe(true);
		const stars = [...root.querySelectorAll("[data-column='score'] [data-slot='star']")];
		expect(stars.map((star) => star.getAttribute("data-state"))).toEqual(["filled", "filled", "filled", "empty", "empty"]);
	});
});
