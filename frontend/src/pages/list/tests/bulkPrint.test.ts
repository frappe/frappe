import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type App } from "vue";
import type { BulkRun } from "@/shell/bulkRuns";
import { useBulkScope } from "@/list/useBulkScope";
import { useBulkPrint } from "../bulkPrint";
import { NO_LETTERHEAD, PAGE_SIZES, printBody, printableFormats } from "../printOptions";
import PrintDialog from "../PrintDialog.vue";
import { startBulkPrint } from "../printRun";

const fake = vi.hoisted(() => ({
	success: vi.fn(),
	info: vi.fn(),
	error: vi.fn(),
	listDocuments: vi.fn(),
	bulkPrintDocuments: vi.fn(),
	followBulkRun: vi.fn(),
}));

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast: { success: fake.success, info: fake.info, error: fake.error },
}));
vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	listDocuments: fake.listDocuments,
	bulkPrintDocuments: fake.bulkPrintDocuments,
}));
vi.mock("@/shell/bulkRuns", () => ({ followBulkRun: fake.followBulkRun }));

let mounted: App | null = null;

async function settle() {
	for (let turn = 0; turn < 6; turn++) await nextTick();
	await new Promise((resolve) => setTimeout(resolve));
	await nextTick();
}

afterEach(() => {
	mounted?.unmount();
	mounted = null;
	document.body.innerHTML = "";
	vi.clearAllMocks();
});

describe("printOptions", () => {
	it("offers v1's page sizes", () => {
		expect(PAGE_SIZES).toHaveLength(10 + 11 + 9);
		expect(PAGE_SIZES).toContain("A4");
		expect(PAGE_SIZES).toContain("B10");
	});

	it("drops the formats that do not print a PDF page", () => {
		const rows = [
			{ name: "Plain" },
			{ name: "Script", print_format_type: "JS" },
			{ name: "Of a report", print_format_for: "Report" },
			{ name: "Label", raw_printing: 1 },
		];
		expect(printableFormats(rows)).toEqual(["Plain"]);
	});
});

describe("printBody", () => {
	const scope = { names: ["A"] };

	it("leaves a default choice out", () => {
		const body = printBody(scope, { printFormat: "", letterhead: "", pageSize: "" });
		expect(body).toEqual({ names: ["A"] });
	});

	it("sends the chosen format, letterhead and page size", () => {
		const body = printBody(scope, { printFormat: "Invoice", letterhead: "Acme", pageSize: "A5" });
		expect(body).toMatchObject({ print_format: "Invoice", letterhead: "Acme", page_size: "A5" });
		expect(body.no_letterhead).toBeUndefined();
	});

	it("turns No Letterhead into the flag, not a letterhead name", () => {
		const body = printBody(scope, { printFormat: "", letterhead: NO_LETTERHEAD, pageSize: "" });
		expect(body).toMatchObject({ no_letterhead: true });
		expect(body.letterhead).toBeUndefined();
	});
});

describe("useBulkPrint", () => {
	function ask(names: string[], cap: number, extra: { total?: number; approx?: boolean } = {}) {
		let print!: ReturnType<typeof useBulkPrint>;
		const selection = ref(names);
		const rows = names.map((name) => ({ name }));
		const filters = { status: "Open" };
		const scope = useBulkScope({
			selection,
			rows: () => rows,
			filters: () => filters,
			hasNextPage: () => true,
			totalCount: () => extra.total ?? names.length,
			totalApprox: () => extra.approx ?? false,
			exact: () => true,
		});
		const root = document.createElement("div");
		mounted = createApp({
			setup() {
				print = useBulkPrint(scope);
				return () => null;
			},
		});
		mounted.provide("boot", { max_bulk_print_docs: cap }).mount(root);
		return { print, selection, scope };
	}

	it("opens the dialog on a frozen copy of the selection", () => {
		const { print, selection } = ask(["A", "B"], 100);
		print.ask();
		selection.value = ["C"];
		expect(print.open.value).toBe(true);
		expect(print.count.value).toBe(2);
		expect(print.all.value).toBe(false);
		expect(print.scope.value).toEqual({ names: ["A", "B"] });
	});

	it("prints every record the filters show after Select all, and names the total", () => {
		const { print, scope } = ask(["A", "B"], 100, { total: 40, approx: true });
		scope.selectAll();
		print.ask();
		expect(print.scope.value).toEqual({ filters: { status: "Open" } });
		expect([print.count.value, print.all.value, print.approx.value]).toEqual([40, true, true]);
	});

	it("refuses over Print Settings' cap before any request", () => {
		const { print } = ask(["A", "B", "C"], 2);
		print.ask();
		expect(print.mounted.value).toBe(false);
		expect(fake.error).toHaveBeenCalledWith("You can print up to 2 records at a time");
	});

	it("refuses an all-matching print whose total is over the cap, even when the total is a floor", () => {
		const { print, scope } = ask(["A"], 100, { total: 150, approx: true });
		scope.selectAll();
		print.ask();
		expect(print.mounted.value).toBe(false);
		expect(fake.error).toHaveBeenCalledWith("You can print up to 100 records at a time");
	});
});

describe("startBulkPrint", () => {
	it("follows the run and offers the PDF when it settles with one", async () => {
		fake.bulkPrintDocuments.mockResolvedValue({ data: { task_id: "T1", job_id: "J1" } });
		await startBulkPrint("ToDo", { names: ["A"] });
		expect(fake.bulkPrintDocuments).toHaveBeenCalledWith("ToDo", { names: ["A"] });
		expect(fake.followBulkRun).toHaveBeenCalledWith("T1", expect.any(Function));

		const settled = fake.followBulkRun.mock.calls[0][1] as (run: BulkRun) => void;
		const open = vi.spyOn(window, "open").mockReturnValue(null);
		settled({ result: { total: 1, done: ["A"], failed: [], file_url: "/private/files/T1.pdf" } } as BulkRun);
		const options = fake.success.mock.calls[0][1];
		options.action.onClick();
		expect(open).toHaveBeenCalledWith("/private/files/T1.pdf", "_blank", "noopener");
	});

	it("offers nothing when every record failed", async () => {
		fake.bulkPrintDocuments.mockResolvedValue({ data: { task_id: "T1", job_id: "J1" } });
		await startBulkPrint("ToDo", { names: ["A"] });
		const settled = fake.followBulkRun.mock.calls[0][1] as (run: BulkRun) => void;
		settled({ result: { total: 1, done: [], failed: [{ name: "A", error: "x" }] } } as BulkRun);
		expect(fake.success).not.toHaveBeenCalled();
	});
});

describe("PrintDialog", () => {
	async function open() {
		fake.listDocuments.mockImplementation(async (doctype: string) => ({
			data:
				doctype === "Print Format"
					? [{ name: "Invoice" }, { name: "Script", print_format_type: "JS" }]
					: [{ name: "Acme" }],
		}));
		fake.bulkPrintDocuments.mockResolvedValue({ data: { task_id: "T1", job_id: "J1" } });
		const host = document.createElement("div");
		document.body.append(host);
		const shown = ref(true);
		mounted = createApp({
			render: () =>
				h(PrintDialog, {
					modelValue: shown.value,
					"onUpdate:modelValue": (value: boolean) => (shown.value = value),
					doctype: "ToDo",
					count: 2,
					scope: { names: ["A", "B"] },
				}),
		});
		mounted.mount(host);
		await settle();
		return shown;
	}

	const text = () => document.body.textContent ?? "";
	const press = async (label: string) => {
		[...document.body.querySelectorAll("button")].find((b) => b.textContent?.trim() === label)!.click();
		await settle();
	};

	it("names the count and the three choices, and reads the formats and letterheads of the doctype", async () => {
		await open();
		expect(text()).toContain("Print 2 selected records");
		for (const label of ["Print Format", "Letter Head", "Page Size"]) expect(text()).toContain(label);
		expect(fake.listDocuments).toHaveBeenCalledWith(
			"Print Format",
			expect.objectContaining({ filters: { doc_type: "ToDo", disabled: 0 } })
		);
	});

	it("prints the scope with the defaults, follows the run, and closes", async () => {
		const shown = await open();
		await press("Print");
		expect(fake.bulkPrintDocuments).toHaveBeenCalledWith("ToDo", {
			names: ["A", "B"],
			print_format: undefined,
			letterhead: undefined,
			no_letterhead: undefined,
			page_size: undefined,
		});
		expect(fake.info).toHaveBeenCalledWith("Printing in the background");
		expect(shown.value).toBe(false);
	});

	it("keeps the dialog open with the reason when the server refuses", async () => {
		const shown = await open();
		fake.bulkPrintDocuments.mockRejectedValue(new Error("Too many records"));
		await press("Print");
		expect(text()).toContain("Too many records");
		expect(shown.value).toBe(true);
	});
});
