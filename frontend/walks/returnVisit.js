// Return-visit walk: list, record, Back, Forward, then list and record again from the sidebar,
// counting skeletons and field and row paints per step on a normal and a throttled network.
//
//   yarn --cwd frontend walk:return-visit [--json <path>]
//
// Env: BASE_URL (default http://localhost:8000), USR (Administrator), PWD_FRAPPE (admin),
// DOCTYPE (default: the first rail or sidebar doctype with rows), NETWORK (normal | slow;
// unset runs both). Exits 0 when every return step passes on every network, 1 otherwise.

import { writeFileSync } from "node:fs";
import { chromium, request as requestApi } from "playwright";
import { MARKERS, installCounters } from "./paintCounters.js";

const BASE_URL = process.env.BASE_URL || "http://localhost:8000";
const QUIET_MS = 500;
const KILOBITS = 1000 / 8;

const NETWORKS = {
	normal: { capMs: 15000, conditions: null },
	slow: {
		capMs: 120000,
		conditions: {
			offline: false,
			latency: 400,
			downloadThroughput: 400 * KILOBITS,
			uploadThroughput: 400 * KILOBITS,
		},
	},
};

const RETURN_STEPS = [
	"back-to-list",
	"forward-to-record",
	"list-via-sidebar",
	"record-via-sidebar",
];

async function main() {
	const jsonPath = argumentAfter("--json");
	const names = process.env.NETWORK ? [process.env.NETWORK] : Object.keys(NETWORKS);
	const target = await resolveTarget();
	const runs = [];
	for (const name of names) {
		const run = await new ReturnVisitWalk(target, name).run();
		printRun(run);
		runs.push(run);
	}
	if (jsonPath) writeFileSync(jsonPath, JSON.stringify({ target, runs }, null, 2));
	process.exit(runs.every((run) => run.passed) ? 0 : 1);
}

class ReturnVisitWalk {
	constructor(target, network) {
		this.target = target;
		this.network = network;
		this.capMs = NETWORKS[network].capMs;
		this.steps = [];
		this.inFlight = 0;
		this.lastRequestAt = 0;
	}

	async run() {
		const browser = await chromium.launch();
		try {
			const context = await browser.newContext();
			await logIn(context.request);
			await context.addInitScript(installCounters, MARKERS);
			this.page = await context.newPage();
			this.trackRequests();
			await this.throttle(context);
			await this.walk();
		} finally {
			await browser.close();
		}
		const passed = this.steps.every((step) => step.pass !== false);
		return { network: this.network, recordVia: this.recordVia, steps: this.steps, passed };
	}

	async walk() {
		const { listPath } = this.target;
		const listUrl = new URL(listPath, BASE_URL).href;
		await this.step("list-first", () => this.page.goto(listUrl, { waitUntil: "commit" }));
		const row = this.page.locator(MARKERS.row).first();
		this.recordPath = await row.getAttribute("href");
		await this.step("record-first", () => row.click());
		await this.step("back-to-list", () => this.page.goBack({ waitUntil: "commit" }));
		await this.step("forward-to-record", () => this.page.goForward({ waitUntil: "commit" }));
		await this.step("list-via-sidebar", () => this.sidebarLink(listPath).click());
		const recordLink = this.sidebarLink(this.recordPath);
		this.recordVia = (await recordLink.count()) ? "sidebar" : "row";
		const link = this.recordVia === "sidebar" ? recordLink : this.rowLink(this.recordPath);
		await this.step("record-via-sidebar", () => link.click());
	}

	async step(name, action) {
		const started = Date.now();
		if (this.recordPath)
			await this.page.evaluate((path) => window.__walk.reset(path), this.recordPath);
		await action();
		const ready = await this.page
			.waitForSelector(name.includes("list") ? MARKERS.row : MARKERS.field, {
				timeout: this.capMs,
			})
			.then(
				() => true,
				() => false
			);
		const settled = ready && (await this.settle(started));
		const counts = await this.page.evaluate(() => window.__walk.read());
		const ms = Math.round(Math.max(counts.changedAtMs, this.lastRequestAt - started));
		this.steps.push(summarize(name, counts, ms, settled));
	}

	async settle(started) {
		while (Date.now() - started < this.capMs) {
			const { quietMs } = await this.page.evaluate(() => window.__walk.read());
			const networkQuiet = !this.inFlight && Date.now() - this.lastRequestAt >= QUIET_MS;
			if (networkQuiet && quietMs >= QUIET_MS) return true;
			await this.page.waitForTimeout(100);
		}
		return false;
	}

	trackRequests() {
		const counted = (request) => !request.url().includes("/socket.io/");
		const finish = (request) => {
			if (!counted(request)) return;
			this.inFlight -= 1;
			this.lastRequestAt = Date.now();
		};
		this.page.on("request", (request) => counted(request) && (this.inFlight += 1));
		this.page.on("requestfinished", finish);
		this.page.on("requestfailed", finish);
	}

	async throttle(context) {
		const conditions = NETWORKS[this.network].conditions;
		if (!conditions) return;
		const session = await context.newCDPSession(this.page);
		await session.send("Network.enable");
		await session.send("Network.emulateNetworkConditions", conditions);
	}

	sidebarLink(path) {
		return this.page.locator(`[data-key] a[href=${JSON.stringify(path)}]`).first();
	}

	rowLink(path) {
		return this.page.locator(`${MARKERS.row}[href=${JSON.stringify(path)}]`).first();
	}
}

async function resolveTarget() {
	const request = await requestApi.newContext();
	await logIn(request);
	const index = await getMethod(request, "frappe.shell.boot.get_boot", { path: "/apps" });
	const desk = index.apps.find((entry) => entry.app === "frappe");
	const boot = await getMethod(request, "frappe.shell.boot.get_boot", { path: desk.route });
	const addresses = await getMethod(request, "frappe.shell.doctypes.get_addresses", {
		v: boot.metadata_version,
	});
	const candidates = navigationDoctypes(boot.navigation).filter(
		(doctype) => addresses.doctypes[doctype] && !addresses.singles?.includes(doctype)
	);
	const doctype = process.env.DOCTYPE || (await firstWithRows(request, candidates));
	const [slug, moduleSlug] = addresses.doctypes[doctype];
	const modular = boot.prefixes[desk.prefix].modular;
	await request.dispose();
	return {
		doctype,
		listPath: [desk.route, modular && moduleSlug, slug].filter(Boolean).join("/"),
	};
}

async function logIn(request) {
	const response = await request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: process.env.USR || "Administrator", pwd: process.env.PWD_FRAPPE || "admin" },
	});
	if (!response.ok()) throw new Error(`Login failed with ${response.status()}`);
}

async function getMethod(request, method, params) {
	const response = await request.get(`${BASE_URL}/api/v2/method/${method}`, { params });
	if (!response.ok()) throw new Error(`${method} failed with ${response.status()}`);
	return (await response.json()).data;
}

function navigationDoctypes(navigation) {
	const items = [navigation.rail, ...Object.values(navigation.sidebars ?? {})].flat();
	return items.filter((item) => item.item_type === "DocType").map((item) => item.link_to);
}

async function firstWithRows(request, doctypes) {
	for (const doctype of doctypes) {
		const response = await request.get(`${BASE_URL}/api/v2/document/${doctype}`, {
			params: { limit: 1 },
		});
		if (response.ok() && (await response.json()).data.length) return doctype;
	}
	throw new Error("No doctype in the navigation has rows; set DOCTYPE.");
}

function summarize(name, counts, ms, settled) {
	const fields = paintSummary(counts.fields);
	const rows = paintSummary(counts.rows);
	const step = {
		step: name,
		skeletons: counts.skeletons,
		maxFieldPaints: fields.max,
		fieldsOverOne: fields.overOne,
		maxRowPaints: rows.max,
		rowsOverOne: rows.overOne,
		rowsPainted: rows.painted,
		fieldsPainted: fields.painted,
		ms,
		settled,
	};
	if (RETURN_STEPS.includes(name))
		step.pass = settled && !step.skeletons && fields.max <= 1 && rows.max <= 1;
	return step;
}

function paintSummary(paints) {
	const entries = Object.entries(paints);
	return {
		painted: entries.length,
		max: Math.max(0, ...entries.map(([, count]) => count)),
		overOne: entries.filter(([, count]) => count > 1).map(([key, count]) => `${key}:${count}`),
	};
}

function printRun(run) {
	console.log(`\n${run.network} network, record reached from the ${run.recordVia}`);
	const header = [
		"step",
		"skel",
		"maxField",
		"maxRow",
		"rows",
		"fields",
		"ms",
		"pass",
		"over one",
	];
	const lines = run.steps.map((step) => [
		step.step,
		step.skeletons,
		step.maxFieldPaints,
		step.maxRowPaints,
		step.rowsPainted,
		step.fieldsPainted,
		step.settled ? step.ms : `>${step.ms}`,
		step.pass === undefined ? "-" : step.pass ? "yes" : "NO",
		[...step.fieldsOverOne, ...step.rowsOverOne].join(" "),
	]);
	for (const line of [header, ...lines])
		console.log(line.map((cell, index) => String(cell).padEnd(index ? 9 : 20)).join(""));
}

function argumentAfter(flag) {
	const index = process.argv.indexOf(flag);
	return index === -1 ? null : process.argv[index + 1];
}

await main();
