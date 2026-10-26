// The click-budget walk: cold loads of home, a list and a record, and the clicks home → list
// (rail) and list → record (row), at a 4x slower CPU. Prints the median tables.

import { chromium } from "playwright";
import { writeFileSync } from "node:fs";
import { BASE_URL, NETWORKS, logIn } from "./setup.js";

const HOME = process.env.HOME_PATH || "/apps/crm";
const LIST = process.env.LIST_PATH || "/apps/crm/crm-lead";
const RECORD = process.env.RECORD_PATH || "/apps/crm/crm-lead/CRM-LEAD-2026-00006";
const RUNS = Number(process.env.RUNS || 5);
const SLOW_RUNS = Number(process.env.SLOW_RUNS || 2);
const ONLY = process.env.ONLY;

const RAIL = '[data-slot="sidebar-rail-item"]';
const ROWS = 'a[data-slot="list-row"][href]';
const FIELDS = "[data-crumbs] button > span[title]";

const SCENARIOS = {
	"cold home": (network) => cold(network, HOME, RAIL),
	"cold list": (network) => cold(network, LIST, ROWS),
	"cold record": (network) => cold(network, RECORD, FIELDS),
	"home → list (rail)": (network) => click(network, HOME, RAIL, `a[href^="${LIST}"]`, ROWS),
	"list → record (row)": (network) => click(network, LIST, ROWS, `a[href="${RECORD}"]`, FIELDS),
};

const results = await walk();
if (process.argv.includes("--json"))
	writeFileSync(
		process.argv[process.argv.indexOf("--json") + 1],
		JSON.stringify(results, null, 1)
	);
printTables(results);

async function walk() {
	const networks = process.env.NETWORK ? [process.env.NETWORK] : Object.keys(NETWORKS);
	const results = {};
	for (const network of networks) {
		for (const [name, run] of Object.entries(SCENARIOS)) {
			if (ONLY && !name.includes(ONLY)) continue;
			const runs = [];
			for (let index = 0; index < (network === "slow" ? SLOW_RUNS : RUNS); index++) {
				runs.push(
					await run(network).catch((error) => ({ error: String(error).split("\n")[0] }))
				);
				console.error(network, name, JSON.stringify(runs.at(-1)));
			}
			results[`${network} | ${name}`] = runs;
		}
	}
	return results;
}

async function cold(network, path, ready) {
	const { browser, page } = await open(network);
	try {
		await page.goto(BASE_URL + path, { waitUntil: "commit" });
		await page.waitForSelector(ready, { timeout: NETWORKS[network].capMs });
		await page.waitForTimeout(network === "slow" ? 4000 : 1500);
		const probe = await page.evaluate(() => window.__budget);
		const content = probe.frames.rows ?? probe.frames.fields;
		return {
			rail: probe.frames.rail,
			sidebar: probe.frames.sidebar,
			skeleton: probe.frames.skeleton,
			pageCode: await scriptsDoneBefore(page, content),
			content,
			cls: layoutShift(probe.shifts),
		};
	} finally {
		await browser.close();
	}
}

async function click(network, from, fromReady, link, ready) {
	const { browser, page } = await open(network);
	try {
		await page.goto(BASE_URL + from, { waitUntil: "commit" });
		await page.waitForSelector(fromReady, { timeout: NETWORKS[network].capMs });
		await page.waitForTimeout(network === "slow" ? 4000 : 1500);
		await page.evaluate((selector) => (window.__budget.ready = selector), ready);
		await page.locator(link).first().click();
		await page.waitForSelector(ready, { timeout: NETWORKS[network].capMs });
		await page.waitForTimeout(500);
		const { click: clicked, shifts } = await page.evaluate(() => window.__budget);
		return {
			address: clicked.pushed - clicked.at,
			frame: clicked.frame - clicked.at,
			paint: clicked.paint ?? null,
			drawn: clicked.drawn - clicked.at,
			cls: layoutShift(shifts.filter((shift) => shift.t > clicked.at)),
		};
	} finally {
		await browser.close();
	}
}

async function open(network) {
	const browser = await chromium.launch();
	const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
	if (process.env.SID) {
		const { hostname } = new URL(BASE_URL);
		await context.addCookies([
			{ name: "sid", value: process.env.SID, domain: hostname, path: "/" },
		]);
	} else {
		await logIn(context.request);
	}
	await context.addInitScript(probe);
	const page = await context.newPage();
	const cdp = await context.newCDPSession(page);
	await cdp.send("Network.enable");
	const { conditions } = NETWORKS[network];
	if (conditions) await cdp.send("Network.emulateNetworkConditions", conditions);
	await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
	return { browser, page };
}

/** The last JS or CSS response before the content drew: when the page's code was in. */
function scriptsDoneBefore(page, content) {
	return page.evaluate((before) => {
		const ends = performance
			.getEntriesByType("resource")
			.filter((entry) => /\.(js|css)$/.test(new URL(entry.name).pathname))
			.map((entry) => entry.responseEnd)
			.filter((end) => end <= before);
		return ends.length ? Math.max(...ends) : null;
	}, content);
}

// Runs in the page before any script: one sample per animation frame.
function probe() {
	const budget = { shifts: [], frames: {}, click: null, ready: null };
	window.__budget = budget;
	performance.setResourceTimingBufferSize(5000);

	new PerformanceObserver((list) => {
		for (const entry of list.getEntries())
			budget.shifts.push({
				t: entry.startTime,
				value: entry.value,
				input: entry.hadRecentInput,
			});
	}).observe({ type: "layout-shift", buffered: true });

	new PerformanceObserver((list) => {
		for (const entry of list.getEntries())
			if (entry.name === "click" && budget.click && budget.click.paint === undefined)
				budget.click.paint = entry.duration;
	}).observe({ type: "event", durationThreshold: 16 });

	let contentChangedAt = null;
	new MutationObserver((records) => {
		if (!budget.click || budget.click.frame !== undefined) return;
		const content = document.querySelector('[data-slot="desktop-shell-content"]');
		if (records.some((record) => content?.contains(record.target)))
			contentChangedAt ??= performance.now();
	}).observe(document, { childList: true, subtree: true });

	document.addEventListener(
		"click",
		() => {
			budget.click = { at: performance.now() };
			contentChangedAt = null;
		},
		true
	);
	const pushState = history.pushState;
	history.pushState = function (...args) {
		if (budget.click && budget.click.pushed === undefined)
			budget.click.pushed = performance.now();
		return pushState.apply(this, args);
	};

	const seen = (key, selector) => {
		if (budget.frames[key] === undefined && document.querySelector(selector))
			budget.frames[key] = performance.now();
	};
	const sample = () => {
		const now = performance.now();
		seen("rail", '[data-slot="sidebar-rail-item"]');
		seen("sidebar", '[data-slot="sidebar"]');
		seen("skeleton", '.fui-skeleton, .animate-pulse, [role="status"]');
		seen("rows", 'a[data-slot="list-row"][href]');
		seen("fields", "[data-crumbs] button > span[title]");
		const clicked = budget.click;
		if (clicked) {
			if (clicked.frame === undefined && contentChangedAt !== null) clicked.frame = now;
			if (clicked.drawn === undefined && document.querySelector(budget.ready))
				clicked.drawn = now;
		}
		requestAnimationFrame(sample);
	};
	requestAnimationFrame(sample);
}

/** Cumulative layout shift: the worst session window (1 s gap, 5 s cap). */
function layoutShift(shifts) {
	let worst = 0;
	let window = 0;
	let start = 0;
	let last = -Infinity;
	for (const shift of shifts.filter((shift) => !shift.input)) {
		if (shift.t - last > 1000 || shift.t - start > 5000) {
			window = 0;
			start = shift.t;
		}
		window += shift.value;
		last = shift.t;
		worst = Math.max(worst, window);
	}
	return worst;
}

function printTables(results) {
	const rows = (names, columns) =>
		Object.keys(NETWORKS).flatMap((network) =>
			names
				.map((name) => [
					name,
					(results[`${network} | ${name}`] ?? []).filter((run) => !run.error),
				])
				.filter(([, runs]) => runs.length)
				.map(([name, runs]) => {
					const cells = columns.map((key) =>
						key === "cls" ? shift(median(runs, key)) : time(median(runs, key))
					);
					return `| ${network} | ${name} | ${cells.join(" | ")} | ${runs.length} |`;
				})
		);
	const names = Object.keys(SCENARIOS);
	console.log(
		"| Network | Page | Rail | Sidebar | First skeleton | Page code in | Content | Layout shift | Runs |"
	);
	console.log("| --- | --- | --- | --- | --- | --- | --- | --- | --- |");
	console.log(
		rows(
			names.filter((name) => name.startsWith("cold")),
			["rail", "sidebar", "skeleton", "pageCode", "content", "cls"]
		).join("\n")
	);
	console.log();
	console.log(
		"| Network | Click | Address changes | Frame changes | Click to next paint | Page drawn | Layout shift | Runs |"
	);
	console.log("| --- | --- | --- | --- | --- | --- | --- | --- |");
	console.log(
		rows(
			names.filter((name) => !name.startsWith("cold")),
			["address", "frame", "paint", "drawn", "cls"]
		).join("\n")
	);
	const failed = Object.entries(results).filter(([, runs]) => runs.some((run) => run.error));
	for (const [name, runs] of failed)
		console.log(`\n${name}: ${runs.filter((run) => run.error).length} failed`);
}

function median(runs, key) {
	const values = runs
		.map((run) => run[key])
		.filter(Number.isFinite)
		.sort((a, b) => a - b);
	if (!values.length) return null;
	const middle = Math.floor(values.length / 2);
	return values.length % 2 ? values[middle] : (values[middle - 1] + values[middle]) / 2;
}

function time(value) {
	if (value === null) return "–";
	return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${Math.round(value)} ms`;
}

function shift(value) {
	return value === null ? "–" : value.toFixed(3);
}
