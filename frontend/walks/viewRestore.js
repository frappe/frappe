// View-restore walk: checks that a return visit to a record shows the scroll offsets, form tab and
// sections the reader left, from its first frame. How to run it: see README.md.

import { writeFileSync } from "node:fs";
import { chromium } from "playwright";
import { printRun } from "./viewReport.js";
import { VIEW, installViewProbe } from "./viewProbe.js";
import { chooseDoctype, removeViewLayouts, storeViewLayouts } from "./viewLayouts.js";
import { BASE_URL, NETWORKS, logIn, setUp } from "./setup.js";

const QUIET_MS = 500;
const TOLERANCE_PX = 1;
const MIN_SCROLL_PX = 40;
const ROW = 'a[data-slot="list-row"][href]';
const SCROLLERS = ["details", "panel"];

async function main() {
	const { jsonPath, networks, target } = await setUp(chooseDoctype);
	const runs = [];
	try {
		const layout = await storeViewLayouts(target.doctype);
		for (const network of networks) {
			const run = await new ViewRestoreWalk(target, layout, network).run();
			printRun(target, layout, run);
			runs.push(run);
		}
	} finally {
		await removeViewLayouts();
	}
	if (jsonPath) writeFileSync(jsonPath, JSON.stringify({ target, runs }, null, 2));
	process.exit(runs.every((run) => run.passed) ? 0 : 1);
}

class ViewRestoreWalk {
	constructor(target, layout, network) {
		Object.assign(this, { target, layout, network, steps: [], inFlight: 0, lastRequestAt: 0 });
		this.capMs = NETWORKS[network].capMs;
	}

	async run() {
		const browser = await chromium.launch();
		try {
			const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
			await logIn(context.request);
			await context.addInitScript(installViewProbe, VIEW);
			this.page = await context.newPage();
			this.page.on("pageerror", (error) => (this.pageError ??= error.message));
			this.trackRequests();
			await this.throttle(context);
			await this.walk();
		} catch (error) {
			this.error = error.message.split("\n")[0];
		} finally {
			await browser.close();
		}
		const passed = !this.error && this.steps.every((step) => step.pass !== false);
		const { network, listVia, recordVia, steps, error, pageError } = this;
		return { network, listVia, recordVia, steps, error, pageError, passed };
	}

	async walk() {
		const listUrl = new URL(this.target.listPath, BASE_URL).href;
		await this.step("list-first", () => this.page.goto(listUrl, { waitUntil: "commit" }));
		await this.pickRecords();
		await this.step("record-first", () => this.rowLink(this.recordPath).click());
		this.expected = await this.arrange();
		await this.step("back-to-list", () => this.page.goBack({ waitUntil: "commit" }));
		const forward = () => this.page.goForward({ waitUntil: "commit" });
		await this.step("forward-to-record", forward, { check: "return" });
		const listLink = await this.listLink();
		await this.step("list-via-nav", () => listLink.click());
		const back = () => this.page.goBack({ waitUntil: "commit" });
		await this.step("back-to-record", back, { check: "return" });
		await this.step("list-via-nav-again", () => listLink.click());
		const recordLink = await this.returnLink();
		await this.step("record-via-nav", () => recordLink.click(), { check: "return" });
		await this.step("list-before-new", () => listLink.click());
		const fresh = () => this.rowLink(this.freshPath).click();
		await this.step("new-record", fresh, { check: "fresh", path: this.freshPath });
	}

	async pickRecords() {
		const hrefs = await this.page
			.locator(ROW)
			.evaluateAll((rows) => rows.map((row) => row.getAttribute("href")));
		[this.recordPath] = hrefs;
		this.freshPath = hrefs.slice(1).at(Math.min(1, hrefs.length - 2));
		if (!this.freshPath)
			throw new Error(`The ${this.target.doctype} list shows fewer than two rows`);
	}

	/** The first visit's view: a later form tab, its closed section opened, both scrollers mid-way. */
	async arrange() {
		const { tab, section } = this.layout;
		await this.page.locator(VIEW.form).getByRole("tab", { name: tab, exact: true }).click();
		const selected = (label) => window.__view.read().tab === label;
		await this.until(selected, tab, `Form tab "${tab}" was not selected after a click`);
		const state = await this.sectionState(section);
		if (state !== "closed")
			throw new Error(
				`Section "${section}" shows ${state} on arrival, not closed; another Details layout wins`
			);
		await this.page
			.locator(VIEW.form)
			.locator(VIEW.header, { hasText: exactText(section) })
			.first()
			.click();
		await this.until(
			(label) =>
				window.__view.read().sections.some((s) => s.label === label && s.state === "open"),
			section,
			`Section "${section}" did not open after a click`
		);
		for (const name of SCROLLERS) await this.scrollHalfway(name);
		await this.settle(Date.now());
		return this.page.evaluate(() => window.__view.read());
	}

	async scrollHalfway(name) {
		const range = await this.page.evaluate((scroller) => {
			const element = window.__view.scroller(scroller);
			if (!element) return null;
			const max = element.scrollHeight - element.clientHeight;
			element.scrollTop = Math.round(max / 2);
			return max;
		}, name);
		if (range === null) throw new Error(`No ${name} scroller on the record page`);
		if (range < MIN_SCROLL_PX)
			throw new Error(
				`The ${name} scroller can move only ${range} px; choose another DOCTYPE`
			);
	}

	async step(name, action, { check, path = this.recordPath } = {}) {
		const started = Date.now();
		await this.page.evaluate((recordPath) => window.__view?.reset(recordPath), path ?? "");
		await action();
		const settled = (await this.ready(name)) && (await this.settle(started));
		const ms = Date.now() - started;
		const step = { step: name, ms, settled };
		if (check) {
			const [view, frames] = await this.page.evaluate(() => [
				window.__view.read(),
				window.__view.frames(),
			]);
			const result =
				check === "return" ? this.returnCheck(view, frames) : this.freshCheck(view);
			Object.assign(step, { view, frameCount: frames.length }, result);
			step.pass = settled && step.pass;
		}
		this.steps.push(step);
	}

	returnCheck(view, frames) {
		const offsets = SCROLLERS.map((name) => {
			const got = view[name];
			const near = (value) => value !== null && Math.abs(value - got) <= TOLERANCE_PX;
			const off = frames.map((frame) => frame[name]).filter((value) => !near(value));
			const want = this.expected[name];
			const ok = got !== null && Math.abs(got - want) <= TOLERANCE_PX;
			return { name, want, got, ok, framesOff: off.length, firstOff: off[0] ?? null };
		});
		const tabOk = view.tab === this.expected.tab;
		const sectionsOff = sectionsDiffer(view.sections, this.expected.sections);
		const sectionsOk = !sectionsOff.length;
		const framesOk = offsets.every((offset) => !offset.framesOff);
		const pass = offsets.every((offset) => offset.ok) && framesOk && tabOk && sectionsOk;
		return { offsets, tabOk, sectionsOk, sectionsOff, framesOk, pass };
	}

	/** A record never seen opens at the top, every section as its layout starts it. */
	freshCheck(view) {
		const offsets = SCROLLERS.map((name) => {
			const got = view[name];
			return { name, want: 0, got, ok: got !== null && got <= TOLERANCE_PX };
		});
		const closed = (label) => view.tab === this.layout.tab && label === this.layout.section;
		const defaults = view.sections.map(({ label }) => ({
			label,
			state: closed(label) ? "closed" : "open",
		}));
		const sectionsOff = sectionsDiffer(view.sections, defaults);
		const sectionsOk = !sectionsOff.length;
		const pass = offsets.every((offset) => offset.ok) && sectionsOk;
		return { offsets, sectionsOk, sectionsOff, pass };
	}

	async sectionState(label) {
		const { sections } = await this.page.evaluate(() => window.__view.read());
		return sections.find((section) => section.label === label)?.state ?? "missing";
	}

	async until(predicate, arg, failure) {
		const options = { timeout: this.capMs };
		await this.page.waitForFunction(predicate, arg, options).catch(() => {
			throw new Error(failure);
		});
	}

	ready(name) {
		const selector = name.includes("list") ? ROW : VIEW.content;
		return this.page.waitForSelector(selector, { timeout: this.capMs }).then(
			() => true,
			() => false
		);
	}

	async settle(started) {
		while (Date.now() - started < this.capMs) {
			const quietMs = await this.page.evaluate(() => window.__view.quietMs());
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

	async listLink() {
		const path = this.target.listPath;
		const crumb = this.link("[data-crumbs] a", path);
		const found = await this.firstVisible({ ...this.navigationLinks(path), crumb });
		if (!found)
			throw new Error(
				`No rail, sidebar or breadcrumb link to the ${this.target.doctype} list`
			);
		this.listVia = found.via;
		return found.locator;
	}

	async returnLink() {
		const found = await this.firstVisible(this.navigationLinks(this.recordPath));
		this.recordVia = found?.via ?? "row";
		return found?.locator ?? this.rowLink(this.recordPath);
	}

	rowLink(path) {
		return this.link(ROW, path);
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

function sectionsDiffer(shown, wanted) {
	if (shown.length !== wanted.length)
		return [`${shown.length} sections shown, wanted ${wanted.length}`];
	return shown
		.map((section, index) => [section, wanted[index]])
		.filter(([section, want]) => section.label !== want.label || section.state !== want.state)
		.map(
			([section, want]) =>
				`"${section.label}" ${section.state}, wanted "${want.label}" ${want.state}`
		);
}

function exactText(text) {
	const escaped = text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
	return new RegExp(`^\\s*${escaped}\\s*$`);
}

await main();
