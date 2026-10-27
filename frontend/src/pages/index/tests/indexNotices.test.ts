// The index's notices: corner cards, the bell they tuck into for the tab, and when each is done.
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type App } from "vue";
import type { Boot } from "@/boot";
import IndexNotices from "../IndexNotices.vue";
import IndexPage from "../IndexPage.vue";
import type { IndexNoticeList } from "../notices";

const fake = vi.hoisted(() => ({ runMethod: vi.fn() }));

vi.mock("@framework/ui/api", async (original) => ({
	...(await original<object>()),
	runMethod: fake.runMethod,
}));

const USER = "manager@example.com";

const NOTICES: IndexNoticeList = {
	setup: { apps: ["Frappe Framework", "ERPNext"], route: "/desk/setup-wizard" },
	whats_new: [{ title: "ERPNext", version: "17.1.0" }],
};

const NOTES = [
	{
		title: "ERPNext",
		version: "17.1.0",
		notes: [{ version: "17.1.0", html: "<h3>Stock</h3><p>Faster <b>ledgers</b>.</p>" }],
	},
];

const mounted: App[] = [];
let assign: ReturnType<typeof vi.fn>;

beforeAll(() => Promise.all([import("../IndexNotices.vue"), import("../WhatsNewDialog.vue")]));

beforeEach(() => {
	fake.runMethod.mockReset().mockResolvedValue({ data: NOTES });
	assign = vi.fn();
	vi.stubGlobal("location", { ...window.location, assign });
	sessionStorage.clear();
});

afterEach(() => {
	mounted.splice(0).forEach((app) => app.unmount());
	document.body.innerHTML = "";
	vi.unstubAllGlobals();
});

async function flush() {
	for (let tick = 0; tick < 5; tick++) await new Promise((resolve) => setTimeout(resolve));
	await nextTick();
}

/** The shell's foot cell, which the bell teleports into, then `component` beside it. */
async function mountWith(component: object, props: Record<string, unknown> = {}, boot?: Boot) {
	const foot = document.createElement("div");
	foot.innerHTML = "<div data-index-foot-notices></div>";
	const host = document.createElement("div");
	document.body.append(foot, host);
	const app = createApp({ render: () => h(component, props) });
	if (boot) app.provide("boot", boot);
	app.mount(host);
	mounted.push(app);
	await flush();
	return { host, foot };
}

function mountNotices(notices: IndexNoticeList = NOTICES) {
	return mountWith(IndexNotices, { notices, user: USER });
}

function cards(host: HTMLElement) {
	return [...host.querySelectorAll<HTMLElement>("[data-notice]")].map((card) => card.dataset.notice);
}

function card(host: HTMLElement, key: string) {
	return host.querySelector<HTMLElement>(`[data-notice="${key}"]`)!;
}

function button(root: HTMLElement, label: string) {
	return [...root.querySelectorAll("button")].find(
		(node) => node.textContent?.trim() === label || node.getAttribute("aria-label") === label
	)!;
}

function bell(foot: HTMLElement) {
	return foot.querySelector<HTMLElement>("[data-index-bell] button");
}

describe("the index's notices", () => {
	it("draws one card per notice in the corner, and no bell", async () => {
		const { host, foot } = await mountNotices();

		expect(cards(host)).toEqual(["setup", "whats_new"]);
		expect(card(host, "setup").textContent).toContain("Finish setting up this site");
		expect(card(host, "setup").textContent).toContain("Frappe Framework, ERPNext");
		expect(card(host, "whats_new").textContent).toContain("ERPNext 17.1.0");
		expect(bell(foot)).toBeNull();
	});

	it("opens the setup wizard by a full load", async () => {
		const { host } = await mountNotices();

		button(card(host, "setup"), "Continue setup").click();

		expect(assign).toHaveBeenCalledWith("/desk/setup-wizard");
	});

	it("tucks a closed card into the bell above the avatar, and a click brings it back", async () => {
		const { host, foot } = await mountNotices();

		button(card(host, "setup"), "Dismiss").click();
		await flush();

		expect(cards(host)).toEqual(["whats_new"]);
		expect(bell(foot)?.getAttribute("aria-label")).toBe("1 notice");

		button(card(host, "whats_new"), "Dismiss").click();
		await flush();
		expect(cards(host)).toEqual([]);
		expect(bell(foot)?.getAttribute("aria-label")).toBe("2 notices");

		bell(foot)!.click();
		await flush();
		expect(cards(host)).toEqual(["setup", "whats_new"]);
		expect(bell(foot)).toBeNull();
	});

	it("keeps a tucked card tucked for the tab, and for this person only", async () => {
		const first = await mountNotices();
		button(card(first.host, "setup"), "Dismiss").click();
		await flush();
		mounted.splice(0).forEach((app) => app.unmount());
		document.body.innerHTML = "";

		const again = await mountNotices();
		expect(cards(again.host)).toEqual(["whats_new"]);
		expect(bell(again.foot)?.getAttribute("aria-label")).toBe("1 notice");

		const other = await mountWith(IndexNotices, { notices: NOTICES, user: "other@example.com" });
		expect(cards(other.host)).toEqual(["setup", "whats_new"]);
	});

	it("opens what's new in a dialog that reads the notes, and drops the notice for good", async () => {
		const { host, foot } = await mountNotices();
		button(card(host, "setup"), "Dismiss").click();
		await flush();

		button(card(host, "whats_new"), "See what's new").click();
		await flush();

		expect(fake.runMethod).toHaveBeenCalledWith("frappe.shell.index_notices.read_whats_new");
		const dialog = document.querySelector<HTMLElement>("[data-whats-new]")!;
		expect(dialog.textContent).toContain("ERPNext 17.1.0");
		expect(dialog.querySelector("b")?.textContent).toBe("ledgers");
		expect(cards(host)).toEqual([]);
		expect(bell(foot)?.getAttribute("aria-label")).toBe("1 notice");
	});

	it("brings the card back when the notes cannot be read", async () => {
		fake.runMethod.mockRejectedValue(new Error("offline"));
		const { host } = await mountNotices();

		button(card(host, "whats_new"), "See what's new").click();
		await flush();

		expect(document.querySelector("[data-whats-new]")).toBeNull();
		expect(cards(host)).toEqual(["setup", "whats_new"]);
	});

	it("leaves out a notice boot does not send", async () => {
		const { host } = await mountNotices({ setup: NOTICES.setup });

		expect(cards(host)).toEqual(["setup"]);
	});
});

describe("the index page's notices", () => {
	function boot(notices?: IndexNoticeList) {
		return {
			app: null,
			apps: [],
			favourites: [],
			recent: [],
			notices,
			session: { timezone: "Asia/Kolkata", user: { name: USER } },
		} as unknown as Boot;
	}

	it("draws the notices boot sends", async () => {
		const { host } = await mountWith(IndexPage, {}, boot(NOTICES));

		expect(cards(host)).toEqual(["setup", "whats_new"]);
	});

	it("draws no notices region for a person boot sends none", async () => {
		const { host } = await mountWith(IndexPage, {}, boot({}));

		expect(host.querySelector("[data-index-notices]")).toBeNull();
	});
});
