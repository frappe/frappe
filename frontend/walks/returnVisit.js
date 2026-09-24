// Return-visit walk: counts skeletons and field and row paints on each step of a return visit.
// How to run it: see README.md.

import { writeFileSync } from "node:fs";
import { chromium } from "playwright";
import { MARKERS, installCounters } from "./paintCounters.js";
import { BASE_URL, NETWORKS, logIn, setUp } from "./setup.js";

const QUIET_MS = 500;

const RETURN_STEPS = [
	"back-to-list",
	"forward-to-record",
	"list-via-sidebar",
	"record-via-sidebar",
];

const COLUMNS = ["step", "skel", "maxField", "maxRow", "rows", "fields", "ms", "pass", "over one"];

async function main() {
	const { jsonPath, networks, target } = await setUp();
	const runs = [];
	for (const name of networks) {
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
		const { network, listVia, recordVia, steps } = this;
		return { network, listVia, recordVia, steps, passed };
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
		const listLink = await this.listLink(listPath);
		await this.step("list-via-sidebar", () => listLink.click());
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

	async listLink(path) {
		const crumb = this.link("[data-crumbs] a", path);
		const found = await this.firstVisible({ ...this.navigationLinks(path), crumb });
		const { doctype } = this.target;
		if (!found) throw new Error(`No rail, sidebar or breadcrumb link to the ${doctype} list`);
		this.listVia = found.via;
		return found.locator;
	}

	async returnLink() {
		const found = await this.firstVisible(this.navigationLinks(this.recordPath));
		this.recordVia = found?.via ?? "row";
		return found?.locator ?? this.link(MARKERS.row, this.recordPath);
	}

	link(selector, path) {
		return this.page.locator(`${selector}[href=${JSON.stringify(path)}]`).first();
	}

	navigationLinks(path) {
		const sidebar = this.link(`[data-slot="sidebar"] [data-key] a`, path);
		const rail = this.link(`[data-slot="sidebar-rail"] [data-key] a`, path);
		return { sidebar, rail };
	}

	async firstVisible(candidates) {
		for (const [via, locator] of Object.entries(candidates))
			if (await locator.isVisible()) return { via, locator };
		return null;
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
	const via = `list reached from the ${run.listVia}, record from the ${run.recordVia}`;
	write(`\n${run.network} network, ${via}`);
	printLine(COLUMNS);
	for (const step of run.steps) {
		printLine(tableCells(step));
		if (step.skeletons) write(`${"".padEnd(20)}skeletons: ${markerList(step)}`);
	}
}

function write(text) {
	process.stdout.write(`${text}\n`);
}

function printLine(cells) {
	write(cells.map((cell, index) => String(cell).padEnd(index ? 9 : 20)).join(""));
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
