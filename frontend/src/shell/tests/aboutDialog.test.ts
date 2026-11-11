import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type App } from "vue";
import type { Boot } from "@/boot";
import AboutDialog from "../AboutDialog.vue";

const fake = vi.hoisted(() => ({ runMethod: vi.fn(), success: vi.fn(), error: vi.fn() }));

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	runMethod: fake.runMethod,
}));

vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast: { success: fake.success, error: fake.error },
}));

const VERSIONS = {
	erpnext: { title: "ERPNext", description: "ERP", version: "16.0.0", branch: "pr-9", logo: null },
	frappe: { title: "Frappe Framework", description: "Framework", version: "17.0.0", branch: "develop", logo: null },
	crm: { title: "CRM", description: "Sell more", version: "2.0.0", branch: "main", logo: null },
};

let mounted: App | null = null;

async function open(boot: Partial<Boot>) {
	const host = document.createElement("div");
	document.body.append(host);
	mounted = createApp({ render: () => h(AboutDialog, { open: true }) });
	mounted.provide("boot", { app: "crm", is_fc_site: false, has_app_updates: false, ...boot });
	mounted.mount(host);
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

const text = (selector: string) => document.body.querySelector(selector)?.textContent ?? "";
const keys = () =>
	Array.from(document.body.querySelectorAll("[data-about-apps] > li")).map((li) => li.getAttribute("data-key"));

describe("AboutDialog", () => {
	it("heads with the current app, then lists Frappe Framework and the rest", async () => {
		fake.runMethod.mockResolvedValue({ data: VERSIONS });
		await open({});
		expect(text("[data-about-header]")).toContain("CRM");
		expect(text("[data-about-header]")).toContain("crm: 2.0.0 (main)");
		expect(keys()).toEqual(["frappe", "erpnext"]);
		expect(text("[data-key='erpnext']")).toContain("16.0.0");
		expect(text("[data-key='erpnext']")).not.toContain("pr-9");
	});

	it("falls back to Frappe Framework in the header off a product app", async () => {
		fake.runMethod.mockResolvedValue({ data: VERSIONS });
		await open({ app: "frappe" });
		expect(text("[data-about-header]")).toContain("Frappe Framework");
		expect(keys()).toEqual(["erpnext", "crm"]);
	});

	it("shows Frappe Support and Update Available only on a Frappe Cloud site", async () => {
		fake.runMethod.mockResolvedValue({ data: VERSIONS });
		await open({});
		expect(document.body.querySelector("[data-about-support]")).toBeNull();
		expect(document.body.textContent).not.toContain("Update Available");

		mounted?.unmount();
		document.body.innerHTML = "";
		await open({ is_fc_site: true, has_app_updates: true });
		expect(document.body.querySelector("[data-about-support]")).not.toBeNull();
		expect(document.body.textContent).toContain("Update Available");
	});

	it("copies one app as `app: version`, and every version as a fenced block", async () => {
		fake.runMethod.mockResolvedValue({ data: VERSIONS });
		const writeText = vi.fn().mockResolvedValue(undefined);
		vi.stubGlobal("navigator", { ...navigator, clipboard: { writeText } });
		await open({});

		document.body.querySelector<HTMLElement>("[data-key='erpnext'] button")!.click();
		await nextTick();
		expect(writeText).toHaveBeenLastCalledWith("erpnext: 16.0.0");
		expect(fake.success).toHaveBeenCalledWith("Copied");

		Array.from(document.body.querySelectorAll<HTMLElement>("button"))
			.find((button) => button.textContent?.includes("Copy all versions"))!
			.click();
		await nextTick();
		expect(writeText.mock.calls.at(-1)![0]).toMatch(/^```json\n[\s\S]*"crm": "2.0.0"[\s\S]*\n```$/);
		vi.unstubAllGlobals();
	});

	it("keeps the version and its copy icon in one slot, so a tap on the version copies", async () => {
		fake.runMethod.mockResolvedValue({ data: VERSIONS });
		await open({});
		const slots = Array.from(document.body.querySelectorAll("[data-key] [data-slot=item-suffix]"));
		expect(slots).toHaveLength(2);
		for (const slot of slots) {
			const buttons = slot.querySelectorAll("button");
			expect(buttons).toHaveLength(1);
			expect(buttons[0].textContent).toMatch(/\d+\.\d+\.\d+/);
			expect(buttons[0].querySelector(".lucide-copy")).not.toBeNull();
		}
	});

	it("says so when the versions do not load", async () => {
		fake.runMethod.mockRejectedValue(new Error("boom"));
		await open({});
		expect(document.body.textContent).toContain("Could not load the installed apps: boom");
	});
});
