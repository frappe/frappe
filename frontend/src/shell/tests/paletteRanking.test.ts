// The palette's ranking: three tiers on the label and the hidden keywords, then recency, then the alphabet.
import { beforeEach, describe, expect, it } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import type { PaletteRow } from "../palette";
import { rank } from "../paletteRanking";
import { recentVisits } from "../recentVisits";

const boot = {
	app: "crm",
	shell_base: "/apps/crm",
	session: { user: { name: "reader@example.com" } },
} as unknown as Boot;

const addresses = new Addresses({
	doctypes: { "CRM Deal": ["crm-deal", "fcrm"], "CRM Lead": ["crm-lead", "fcrm"] },
	modules: { fcrm: "FCRM" },
});

function row(label: string, extra: Partial<PaletteRow> = {}): PaletteRow {
	return { id: label, label, run: () => {}, ...extra };
}

function labels(rows: PaletteRow[]) {
	return rows.map((one) => one.label);
}

beforeEach(() => recentVisits.heard([]));

describe("rank", () => {
	it("puts a label that starts with the query first, then a word that does, then any match", () => {
		const rows = [row("Undeal"), row("Mark deal as won"), row("Deal Desk"), row("Nothing")];

		expect(labels(rank(rows, "deal"))).toEqual(["Deal Desk", "Mark deal as won", "Undeal"]);
	});

	it("counts a word after punctuation as a word", () => {
		expect(labels(rank([row("Xactivity"), row("Go to tab: Activity")], "act"))).toEqual([
			"Go to tab: Activity",
			"Xactivity",
		]);
	});

	it("matches the hidden keywords, in their own tiers", () => {
		const rows = [row("Log a call", { keywords: ["CRM"] }), row("Scrm")];

		expect(labels(rank(rows, "crm"))).toEqual(["Log a call", "Scrm"]);
	});

	it("breaks a tie by the row opened last, this tab's visits before the server's, then by the alphabet", async () => {
		const router = createRouter({
			history: createMemoryHistory(boot.shell_base),
			routes: [{ path: "/:doctype", name: "list", component: { render: () => null } }],
		});
		recentVisits.track(router, boot, addresses);
		recentVisits.heard([{ route: `${boot.shell_base}/crm-note`, title: "CRM Note", kind: "list", visited: 0 }]);
		await router.push("/crm-lead");
		await router.push("/crm-deal");
		const href = (path: string) => router.resolve(path).href;
		const rows = [
			row("CRM Note", { href: `${boot.shell_base}/crm-note` }),
			row("CRM Lead", { href: href("/crm-lead") }),
			row("CRM Contact"),
			row("CRM Deal", { href: href("/crm-deal") }),
			row("CRM Activity"),
		];

		expect(labels(rank(rows, "crm"))).toEqual([
			"CRM Deal",
			"CRM Lead",
			"CRM Note",
			"CRM Activity",
			"CRM Contact",
		]);
	});

	it("keeps the given order on an empty query", () => {
		expect(labels(rank([row("B"), row("A")], " "))).toEqual(["B", "A"]);
	});
});
