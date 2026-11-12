// The list draws each column's cell as the record's read-only field shows the value, and a Phone or
// Email column's cells (a Phone field, or a Data field whose options say Phone or Email) with the field actions,
// and a web address with a link that opens it.
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
	{ fieldname: "spent", fieldtype: "Duration", hide_days: 1, hide_seconds: 1 },
	{ fieldname: "at", fieldtype: "Time" },
	{ fieldname: "creation", fieldtype: "Datetime" },
	{ fieldname: "modified", fieldtype: "Datetime" },
	{ fieldname: "closed_on", fieldtype: "Datetime" },
	{ fieldname: "last_active", fieldtype: "Datetime", read_only: 1 },
	{ fieldname: "response_by", fieldtype: "Datetime", read_only: 1 },
	{ fieldname: "locked_on", fieldtype: "Datetime", read_only_depends_on: "eval:doc.active" },
	{ fieldname: "seen_date", fieldtype: "Date", read_only: 1 },
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
	{ fieldname: "task_status", fieldtype: "Select", options: "Todo\nDone" },
	{ fieldname: "priority", fieldtype: "Select", options: "Low\nHigh" },
	{ fieldname: "due_date", fieldtype: "Datetime" },
];

// What an app's `list.js` names for those three columns.
const cells: Record<string, ListCell> = {
	task_status: { icons: { Done: "lucide-circle-check" } },
	priority: { badge: { High: "red" } },
	due_date: { icon: "lucide-calendar", format: "D MMM, hh:mm a" },
};
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
	spent: 93784,
	at: "9:15:30",
	creation: "2026-11-01 10:00:00.604123",
	modified: "2026-11-04 10:00:00.604123",
	closed_on: "2026-11-04 00:44:09.604123",
	last_active: "2026-11-04 08:00:00",
	response_by: "2026-11-04 12:00:00",
	locked_on: "2026-11-04 08:00:00",
	seen_date: "2026-11-04",
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
	_extra: "as sent",
	task_status: "Done",
	priority: "High",
	due_date: "2026-10-25 00:00:00",
};

const original = { ...row };
const originalCells = { ...cells };

const applyBadgeFilters = vi.hoisted(() => vi.fn());

vi.mock("@/list/useListView", async () => {
	const { resolveCell } = await import("@/list/cells");
	const { useBulkScope } = await import("@/list/useBulkScope");
	return {
		useListView: () => {
			const selection = ref<string[]>([]);
			const rows = ref([row]);
			return {
			columns: ref(columns),
			shownColumns: ref(columns),
			rows,
			selection,
			scope: useBulkScope({
				selection,
				rows: () => rows.value as never,
				filters: () => ({}),
				hasNextPage: () => false,
				totalCount: () => 1,
				totalApprox: () => false,
				exact: () => true,
			}),
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
			rowActions: ref([]),
			fieldOf: (fieldname: string) => metaFields.find((field) => field.fieldname === fieldname),
			markOf: (fieldname: string) =>
				fieldname === "agent" ? { source: { kind: "image", field: "user_image" }, key: "agent__mark" } : undefined,
			switchOf: () => false,
			canWrite: () => true,
			cellViewOf: (fieldname: string, value: unknown, one: Record<string, unknown>) =>
				resolveCell(
					cells[fieldname],
					value,
					metaFields.find((field) => field.fieldname === fieldname)?.fieldtype,
					one
				),
			applyBadgeFilters,
			statusThemeOf: (fieldname: string, value: unknown) =>
				fieldname === "status" && value ? "red" : null,
			currencyOf: (fieldname: string) =>
				({ amount: { key: "currency" }, fee: { key: "fee__currency" } })[fieldname],
			linkTitles: ref({ "CRM Deal::D-1": "Acme", "User::ann@example.com": "Ann Lee" }),
			columnsCustomized: ref(false),
			rowLink: () => ({}),
			};
		},
	};
});
vi.mock("@framework/ui/experimental/List", async () => {
	const { defineComponent, h } = await import("vue");
	const stub = () => defineComponent({ setup: () => () => null });
	return {
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
// The sprite is not loaded here; the stub names the icon asked for.
vi.mock("@/icons/Icon.vue", () => ({
	default: defineComponent({
		props: ["name"],
		setup: (props) => () => h("i", { "data-icon": props.name }),
	}),
}));
vi.mock("@/shell/PageState.vue", () => ({ default: defineComponent({ render: () => null }) }));

import type { ListCell } from "@/contributions/types";
import { FieldActionsKey } from "@framework/ui/fields/types";
import { resetSession, setSession } from "@framework/ui/useSession";
import ListView from "../ListView.vue";

const mounted: ReturnType<typeof createApp>[] = [];

function mount(): HTMLElement {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const host = {
		controls: ref(null),
		bar: ref(null),
		selecting: ref(false),
		lists: { bulkActions: { provideBuiltins: () => {}, resolve: () => [], visible: () => [] } },
		onCreate: vi.fn(),
		acts: () => ({ drawn: () => null }),
	};
	const view = { doctype: "CRM Lead", filters: ref([]), sort: ref([]) };
	const app = createApp(
		defineComponent({ render: () => h(ListView, { view: view as never, host: host as never }) })
	);
	app.provide("boot", { bulk_actions: true, bulk_operation_limit: 500, session: { user: { name: "jane@example.com" } } });
	app.provide(FieldActionsKey, {
		for: (field, value, record) => [
			{ act: "a", label: `Call ${field.fieldname} ${value} ${JSON.stringify(record ?? null)}`, run: vi.fn() },
		],
	});
	app.mount(root);
	mounted.push(app);
	return root;
}

afterEach(() => {
	Object.assign(cells, originalCells);
	applyBadgeFilters.mockClear();
	Object.assign(row, original);
	vi.unstubAllEnvs();
	vi.useRealTimers();
	resetSession();
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

	it("draw a status column's value as a coloured badge, and no other cell", async () => {
		const root = mount();
		await nextTick();

		const badge = root.querySelector("[data-column='status'] > div")!;
		expect(badge.textContent?.trim()).toBe("Open");
		expect(badge.className).toContain("red");
		expect(root.querySelector("[data-column='website'] [class*='bg-surface-red']")).toBeNull();
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
		expect(text("taken")).toBe("1d 2h 3m 4s");
		expect(text("spent")).toBe("26h 3m");
		expect(text("at")).toBe("09:15:30");
		expect(text("closed_on")).toBe("04-11-2026 00:44:09");
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
		expect(cell("modified")?.getAttribute("data-tooltip")).toBe("04-11-2026 10:00:00");
		expect(cell("creation")?.textContent).toBe("3 days ago");
		expect(cell("creation")?.getAttribute("data-tooltip")).toBe("01-11-2026 10:00:00");
		// Another Datetime field keeps its absolute value.
		expect(root.querySelector("[data-column='closed_on']")?.textContent?.trim()).toBe("04-11-2026 00:44:09");
		expect(cell("closed_on")).toBeNull();
	});

	it("draw a read-only Datetime as relative time, past or future, and keep editable Datetimes and Dates absolute", async () => {
		vi.useFakeTimers({ toFake: ["Date"] });
		vi.setSystemTime(new Date("2026-11-04T04:33:00Z"));
		setSession({ user: {}, roles: [], lang: "en", timezone: "Asia/Kolkata", defaults: {} } as never);
		const root = mount();
		await nextTick();

		const cell = (column: string) => root.querySelector(`[data-column='${column}'] [data-tooltip]`);
		const plain = (column: string) => root.querySelector(`[data-column='${column}']`)?.textContent?.trim();
		// 08:00 in Asia/Kolkata is 02:30 UTC, two hours back; 12:00 is 06:30 UTC, two hours ahead.
		expect(cell("last_active")?.textContent).toBe("2 hours ago");
		expect(cell("last_active")?.getAttribute("data-tooltip")).toBe("04-11-2026 08:00:00");
		expect(cell("response_by")?.textContent).toBe("in 2 hours");
		// A field made read-only only by read_only_depends_on is editable in meta.
		expect(cell("locked_on")).toBeNull();
		expect(plain("locked_on")).toBe("04-11-2026 08:00:00");
		expect(cell("closed_on")).toBeNull();
		expect(cell("seen_date")).toBeNull();
		expect(plain("seen_date")).toBe("04-11-2026");
	});

	it("keep the absolute value without a site zone, draw a bad or empty stamp as it is, and read clock skew under a minute as a few seconds ago", async () => {
		vi.useFakeTimers({ toFake: ["Date"] });
		vi.setSystemTime(new Date("2026-11-04T04:33:00Z"));
		const cell = async (column: string) => {
			const root = mount();
			await nextTick();
			return root.querySelector(`[data-column='${column}']`)?.textContent?.trim();
		};
		expect(await cell("modified")).toBe("04-11-2026 10:00:00");
		expect(await cell("last_active")).toBe("04-11-2026 08:00:00");

		setSession({ user: {}, roles: [], lang: "en", timezone: "Asia/Kolkata", defaults: {} } as never);
		Object.assign(row, { modified: "garbage", creation: "" });
		expect(await cell("modified")).toBe("garbage");
		expect(await cell("creation")).toBe("");
		Object.assign(row, { last_active: "garbage", response_by: "" });
		expect(await cell("last_active")).toBe("garbage");
		expect(await cell("response_by")).toBe("");
		// 10:03:40 in Asia/Kolkata is 40 seconds ahead of the browser's clock, 10:05 two minutes.
		Object.assign(row, { modified: "2026-11-04 10:03:40", last_active: "2026-11-04 10:03:40" });
		expect(await cell("modified")).toBe("a few seconds ago");
		expect(await cell("last_active")).toBe("a few seconds ago");
		Object.assign(row, { modified: "2026-11-04 10:05:00" });
		expect(await cell("modified")).toBe("in 2 minutes");
	});

	it("draw relative time in the signed-in person's language", async () => {
		vi.useFakeTimers({ toFake: ["Date"] });
		vi.setSystemTime(new Date("2026-11-04T04:33:00Z"));
		setSession({ user: {}, roles: [], lang: "de", timezone: "Asia/Kolkata", defaults: {} } as never);
		Object.assign(row, { modified: "2026-11-04 10:03:40" });
		const root = mount();
		await nextTick();

		const cell = (column: string) => root.querySelector(`[data-column='${column}'] [data-tooltip]`);
		expect(cell("modified")?.textContent).toBe("jetzt");
		expect(cell("creation")?.textContent).toBe("vor 3 Tagen");
		expect(cell("response_by")?.textContent).toBe("in 2 Stunden");
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

	it("draw an app's cells: an icon before the label, a badge, and a dated cell with its calendar icon", async () => {
		const root = mount();
		await nextTick();

		const cell = (column: string) => root.querySelector(`[data-column='${column}']`)!;
		expect(cell("task_status").textContent).toContain("Done");
		expect(cell("task_status").querySelector("[data-icon]")?.getAttribute("data-icon")).toBe("circle-check");
		expect(cell("priority").textContent).toBe("High");
		expect(cell("priority").querySelector("[data-icon]")).toBeNull();
		expect(cell("due_date").textContent).toBe("25 Oct, 12:00 am");
		expect(cell("due_date").querySelector("[data-icon]")?.getAttribute("data-icon")).toBe("calendar");
		expect(cell("due_date").querySelector("[data-tooltip]")?.getAttribute("data-tooltip")).toBe(
			"Sun, Oct 25, 2026 | 12:00 am"
		);
	});

	it("keep the default cell for a value an app's cells do not name, and an empty one", async () => {
		row.priority = "Low";
		row.due_date = "";
		const root = mount();
		await nextTick();

		expect(root.querySelector("[data-column='priority']")!.textContent).toBe("Low");
		expect(root.querySelector("[data-column='due_date']")!.querySelector("[data-icon]")).toBeNull();
	});

	it("draw a badge function's label and theme from the row, and apply its filters on a click", async () => {
		cells.priority = {
			badge: (one) => ({ label: `${one.priority} first`, theme: "red", filters: [["priority", "=", "High"]] }),
		};
		const root = mount();
		await nextTick();

		const button = root.querySelector<HTMLButtonElement>("[data-column='priority'] button")!;
		expect(button.textContent?.trim()).toBe("High first");
		button.click();
		expect(applyBadgeFilters).toHaveBeenCalledWith([["priority", "=", "High"]]);
	});

	it("draw a badge function without filters as a plain badge, not a button", async () => {
		cells.priority = { badge: () => ({ theme: "blue" }) };
		const root = mount();
		await nextTick();

		expect(root.querySelector("[data-column='priority'] button")).toBeNull();
		expect(root.querySelector("[data-column='priority']")!.textContent?.trim()).toBe("High");
	});
});
