// Return-visit walk: list, record, Back, Forward, then list and record again from the sidebar,
// counting skeletons and field and row paints per step on a normal and a throttled network.
//
//   yarn --cwd frontend/walks install && yarn --cwd frontend/walks playwright install chromium
//   yarn --cwd frontend/walks walk [--json <path>]
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

const COLUMNS = ["step", "skel", "maxField", "maxRow", "rows", "fields", "ms", "pass", "over one"];

async function main() {
	const jsonPath = argumentAfter("--json");
	const names = networkNames();
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

function argumentAfter(flag) {
	const index = process.argv.indexOf(flag);
	return index === -1 ? null : process.argv[index + 1];
}

function networkNames() {
	const name = process.env.NETWORK;
	if (!name) return Object.keys(NETWORKS);
	if (!NETWORKS[name])
		throw new Error(`Unknown NETWORK "${name}"; use ${Object.keys(NETWORKS).join(" or ")}`);
	return [name];
}

async function resolveTarget() {
	const request = await requestApi.newContext();
	try {
		await logIn(request);
		const desk = await deskBoot(request);
		const doctype =
			process.env.DOCTYPE || (await firstWithRows(request, navigationDoctypes(desk)));
		return { doctype, listPath: listPathOf(desk, doctype) };
	} finally {
		await request.dispose();
	}
}

async function logIn(request) {
	const response = await request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: process.env.USR || "Administrator", pwd: process.env.PWD_FRAPPE || "admin" },
	});
	if (!response.ok()) throw new Error(`Login failed with ${response.status()}`);
}

async function deskBoot(request) {
	const index = await getMethod(request, "frappe.shell.boot.get_boot", { path: "/apps" });
	const desk = index.apps.find((entry) => entry.app === "frappe");
	const boot = await getMethod(request, "frappe.shell.boot.get_boot", { path: desk.route });
	const addresses = await getMethod(request, "frappe.shell.doctypes.get_addresses", {
		v: boot.metadata_version,
	});
	const { modular } = boot.prefixes[desk.prefix];
	return { route: desk.route, modular, navigation: boot.navigation, addresses };
}

async function getMethod(request, method, params) {
	const response = await request.get(`${BASE_URL}/api/v2/method/${method}`, { params });
	if (!response.ok()) throw new Error(`${method} failed with ${response.status()}`);
	return (await response.json()).data;
}

function navigationDoctypes({ navigation, addresses }) {
	const items = [navigation.rail, ...Object.values(navigation.sidebars ?? {})].flat();
	return items
		.filter((item) => item.item_type === "DocType")
		.map((item) => item.link_to)
		.filter((doctype) => addresses.doctypes[doctype] && !addresses.singles?.includes(doctype));
}

async function firstWithRows(request, doctypes) {
	for (const doctype of doctypes) {
		const url = `${BASE_URL}/api/v2/document/${encodeURIComponent(doctype)}`;
		const response = await request.get(url, { params: { limit: 1 } });
		if (response.ok() && (await response.json()).data.length) return doctype;
	}
	throw new Error("No doctype in the navigation has rows; set DOCTYPE.");
}

function listPathOf(desk, doctype) {
	const address = desk.addresses.doctypes[doctype];
	if (!address) throw new Error(`DOCTYPE ${doctype} has no desk address`);
	const [slug, moduleSlug] = address;
	return [desk.route, desk.modular && moduleSlug, slug].filter(Boolean).join("/");
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

	trackRequests() {
		const counted = (request) => !request.url().includes("/socket.io/");
		const finish = (request) => {
			if (!counted(request)) return;
			this.inFlight -= 1;
			this.lastRequestAt = Date.now();
		};
		this.page.on("request", (request) => {
			if (counted(request)) this.inFlight += 1;
		});
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
		const link = await this.returnLink();
		await this.step("record-via-sidebar", () => link.click());
	}

	async step(name, action) {
		const started = Date.now();
		if (this.recordPath)
			await this.page.evaluate((path) => window.__walk.reset(path), this.recordPath);
		await action();
		const settled = (await this.ready(name)) && (await this.settle(started));
		const counts = await this.page.evaluate(() => window.__walk.read());
		const ms = Math.round(Math.max(counts.changedAtMs, this.lastRequestAt - started));
		this.steps.push(summarize(name, counts, ms, settled));
	}

	ready(name) {
		const selector = name.includes("list") ? MARKERS.row : MARKERS.field;
		return this.page.waitForSelector(selector, { timeout: this.capMs }).then(
			() => true,
			() => false
		);
	}

	async settle(started) {
		while (Date.now() - started < this.capMs) {
			const quietMs = await this.page.evaluate(() => window.__walk.quietMs());
			const networkQuiet = !this.inFlight && Date.now() - this.lastRequestAt >= QUIET_MS;
			if (networkQuiet && quietMs >= QUIET_MS) return true;
			await this.page.waitForTimeout(100);
		}
		return false;
	}

	sidebarLink(path) {
		return this.page.locator(`[data-key] a[href=${JSON.stringify(path)}]`).first();
	}

	async returnLink() {
		const sidebar = this.sidebarLink(this.recordPath);
		this.recordVia = (await sidebar.count()) ? "sidebar" : "row";
		return this.recordVia === "sidebar" ? sidebar : this.rowLink(this.recordPath);
	}

	rowLink(path) {
		return this.page.locator(`${MARKERS.row}[href=${JSON.stringify(path)}]`).first();
	}
}

function summarize(name, counts, ms, settled) {
	const fields = paintSummary(counts.fields);
	const rows = paintSummary(counts.rows);
	const step = {
		step: name,
		skeletons: counts.skeletons,
		skeletonMarkers: counts.skeletonMarkers,
		maxFieldPaints: fields.max,
		fieldsOverOne: fields.overOne,
		maxRowPaints: rows.max,
		rowsOverOne: rows.overOne,
		rowsPainted: rows.painted,
		fieldsPainted: fields.painted,
		fieldPaints: counts.fields,
		rowPaints: counts.rows,
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
	printLine(COLUMNS);
	for (const step of run.steps) {
		printLine(tableCells(step));
		if (step.skeletons) console.log(`${"".padEnd(20)}skeletons: ${markerList(step)}`);
	}
}

function printLine(cells) {
	console.log(cells.map((cell, index) => String(cell).padEnd(index ? 9 : 20)).join(""));
}

function tableCells(step) {
	return [
		step.step,
		step.skeletons,
		step.maxFieldPaints,
		step.maxRowPaints,
		step.rowsPainted,
		step.fieldsPainted,
		step.settled ? step.ms : `>${step.ms}`,
		step.pass === undefined ? "-" : step.pass ? "yes" : "NO",
		[...step.fieldsOverOne, ...step.rowsOverOne].join(" "),
	];
}

function markerList(step) {
	const entries = Object.entries(step.skeletonMarkers);
	return entries.map(([marker, count]) => `${marker} x${count}`).join(", ");
}

await main();
