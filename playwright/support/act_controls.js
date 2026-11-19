// The act-control check: every visible button and menu item on a desk v2 page names an act the page can run
// (`data-act`) or says it only changes the view (`data-view`), and every button has an accessible name.
import fs from "fs";
import { execFileSync } from "child_process";
import path from "path";

const OPEN_MS = 400;
// The shell's own menus are the same on every page: the shell test scans them, the others leave them out.
const SHELL_TRIGGERS =
	'[data-key=user-menu], [data-key=palette-trigger], [aria-label="Framework menu"]';
// A dialog's code loads on its first use, which takes seconds on a busy machine.
const DIALOG_MS = 8000;
const CONFIRM_MS = 2000;
const SETTLE_MS = 1500;
const GAPS = path.join(__dirname, "../../frontend/act-gaps.json");

export function read_gaps() {
	return JSON.parse(fs.readFileSync(GAPS, "utf8"));
}

// Gaps in the working copy that the base branch's list does not have, as "kind: name". `null` when the base
// has no readable list (the file is new, or there is no base ref): the check then has nothing to compare.
export function added_gaps(gaps) {
	const base = base_gaps();
	if (!base) return null;
	return Object.entries(gaps).flatMap(([kind, names]) =>
		names
			.filter((name) => !(base[kind] || []).includes(name))
			.map((name) => `${kind}: ${name}`)
	);
}

function base_gaps() {
	for (const ref of [process.env.ACT_GAPS_BASE, "origin/desk-v2", "upstream/desk-v2"]) {
		if (!ref) continue;
		try {
			const text = execFileSync("git", ["show", `${ref}:frontend/act-gaps.json`], {
				cwd: path.dirname(GAPS),
				encoding: "utf8",
				stdio: ["ignore", "pipe", "ignore"],
			});
			return JSON.parse(text);
		} catch {
			// Try the next ref.
		}
	}
	return null;
}

// One problem per control: `{ control, problem }`. `control` is the accessible name, or "(no name)".
// Some controls draw late (a quick filter's operator toggle), so read until two reads in a row agree.
export async function find_problems(page) {
	let last = await read_problems(page);
	for (let again = 0; again < 15; again++) {
		await page.waitForTimeout(400);
		const next = await read_problems(page);
		if (JSON.stringify(next) === JSON.stringify(last)) return next;
		last = next;
	}
	return last;
}

async function read_problems(page) {
	const listed = new Set(
		(await page.evaluate(() => window.desk.acts.list())).map((act) => act.name)
	);
	const found = await page.evaluate(read_controls);
	const problems = [];
	for (const control of found) {
		if (!control.name)
			problems.push({ control: "(no name)", problem: "has no accessible name" });
		if (control.view) continue;
		if (!control.act)
			problems.push({
				control: control.name || "(no name)",
				problem: "has neither data-act nor data-view",
			});
		// A disabled control's act is not listed while it has nothing to do (Undo with no edit, Save with no change).
		else if (!control.disabled && !listed.has(control.act))
			problems.push({
				control: control.name,
				problem: `names ${control.act}, which acts.list() does not list`,
			});
	}
	return problems;
}

// Scans every menu and popover the page opens from a button: the buttons that declare a popup (`aria-haspopup`)
// and `extra` (accessible names of buttons that open one without declaring it). A submenu row opens too.
// `scope` is a selector that limits which buttons are tried, `shell` is false (leave the shell's menus out), true or "only". One scan per button name, so a row menu on each of 20 rows costs one. Returns the problems and the names opened.
export async function scan_menus(page, { extra = [], scope = "body", shell = false } = {}) {
	const problems = [];
	const seen = new Set();
	// A trigger can redraw when another menu closes, so each is found again just before its click.
	for (const { name } of await popup_triggers(page, { extra, scope, shell })) {
		if (seen.has(name)) continue;
		seen.add(name);
		if (!(await click_trigger(page, name, { extra, scope, shell }))) continue;
		await page.waitForTimeout(OPEN_MS);
		problems.push(...(await find_problems(page)));
		problems.push(...(await scan_submenus(page)));
		await close_popups(page);
	}
	return { problems, opened: [...seen] };
}

// A trigger can redraw as a menu closes, which fails a click: find it again and click once more.
async function click_trigger(page, name, options) {
	for (let attempt = 0; attempt < 3; attempt++) {
		const trigger = (await popup_triggers(page, options)).find((t) => t.name === name);
		if (!trigger) return false;
		try {
			await page.locator(`[data-scan-trigger="${trigger.id}"]`).click({ timeout: 5000 });
			return true;
		} catch (error) {
			if (attempt === 2) throw error;
			await close_popups(page);
		}
	}
}

async function popup_triggers(page, options) {
	return page.evaluate(
		({ extra, scope, shell, shell_triggers }) => {
			for (const old of document.querySelectorAll("[data-scan-trigger]"))
				delete old.dataset.scanTrigger;
			let id = 0;
			return [...document.querySelectorAll(`${scope} button`)]
				.filter((el) => {
					const box = el.getBoundingClientRect();
					const popup = el.getAttribute("aria-haspopup");
					const name = el.getAttribute("aria-label") || el.textContent.trim();
					return (
						box.width > 0 &&
						box.height > 0 &&
						!el.closest(
							"[inert], [aria-hidden=true], [role=menu], [role=dialog], [data-fieldname]"
						) &&
						(shell === "only"
							? el.matches(shell_triggers)
							: shell || !el.matches(shell_triggers)) &&
						((popup && popup !== "false") || extra.includes(name))
					);
				})
				.map((el) => {
					el.dataset.scanTrigger = String(++id);
					return { id, name: el.getAttribute("aria-label") || el.textContent.trim() };
				});
		},
		{ ...options, shell_triggers: SHELL_TRIGGERS }
	);
}

// A right click on a list row opens the row's menu (and selects the row).
export async function scan_row_menu(page) {
	await page.locator("a[role=row]").first().click({ button: "right" });
	await page.waitForTimeout(OPEN_MS);
	const problems = await find_problems(page);
	await close_popups(page);
	return problems;
}

// A submenu row opens on hover or a click; its rows are the problems, and the parent menu stays open.
async function scan_submenus(page) {
	const problems = [];
	const rows = page.locator("[role=menu] [role=menuitem][aria-haspopup]:visible");
	for (let i = 0; i < (await rows.count()); i++) {
		await rows.nth(i).click();
		await page.waitForTimeout(OPEN_MS);
		problems.push(...(await find_problems(page)));
		await page.keyboard.press("ArrowLeft");
		await page.waitForTimeout(OPEN_MS);
	}
	return problems;
}

// Runs each act that asks for a dialog, a picker or a confirmation with no argument, scans what opens and closes it.
// The shell's acts are the same on every page, so `shell` picks them for one page and leaves them out of the others.
// `restore` puts back what the page had (selected rows) after each act, which can leave the page or clear it.
export async function scan_dialog_acts(page, { shell = false, restore, confirm = true } = {}) {
	const problems = [];
	const acts = await page.evaluate(
		async ([shell, confirm]) =>
			(
				await window.desk.acts.list()
			)
				.filter((act) => act.name.startsWith("shell.") === shell)
				.filter((act) =>
					(act.asks || []).some((ask) =>
						["dialog", "picker", ...(confirm ? ["confirm", "danger"] : [])].includes(
							ask
						)
					)
				)
				.map((act) => ({
					name: act.name,
					lazy: act.asks.some((ask) => ask === "dialog" || ask === "picker"),
				})),
		[shell, confirm]
	);
	for (const { name, lazy } of acts) {
		const url = page.url();
		// Closing a dialog can clear what the page had (the list's selected rows).
		await restore?.(page);
		// Not awaited: the act's call ends when the dialog closes. The export dialog is not in `dialogs()`.
		await page.evaluate((name) => void window.desk.acts.run(name), name);
		const opened = await page
			.waitForFunction(
				async () =>
					(await window.desk.dialogs()).length > 0 ||
					!!document.querySelector("[role=dialog] button"),
				null,
				// A confirmation is small and always loaded; an act that opens none is not worth the long wait.
				{ timeout: lazy ? DIALOG_MS : CONFIRM_MS }
			)
			.then(
				() => true,
				() => false
			);
		if (!opened) {
			// A late dialog must not open over the next act.
			await close_popups(page);
			continue;
		}
		// The dialog's frame can show before its content does.
		await page.waitForSelector("[role=dialog] button", { timeout: DIALOG_MS }).catch(() => {});
		await page.waitForTimeout(OPEN_MS);
		problems.push(...(await find_problems(page)));
		await close_popups(page);
		if (page.url() !== url) {
			await page.goto(url);
			await settle(page);
		}
	}
	return problems;
}

// Waits for the page's data and its first draw.
export async function settle(page) {
	await page.waitForFunction(() => window.desk);
	await page.waitForFunction(async () => !(await window.desk.state()).loading);
	// The doctype editor draws "Loading ToDo…" past `state().loading`.
	await page.waitForFunction(() => !/Loading [^\n]*…/.test(document.body.innerText));
	await page.waitForTimeout(SETTLE_MS);
}

// Escape closes a menu, a popover, a dialog, one layer at a time.
async function close_popups(page) {
	for (let layer = 0; layer < 4; layer++) {
		const open = await page.evaluate(
			async () =>
				(await window.desk.dialogs()).length > 0 ||
				!!document.querySelector(
					"[role=menu], [role=dialog], [role=listbox], [data-state=open]"
				)
		);
		if (!open) break;
		await page.keyboard.press("Escape");
		await page.waitForTimeout(OPEN_MS);
	}
	// A closing layer still blocks clicks (`pointer-events: none` on the page) for a moment.
	await page.waitForFunction(() => getComputedStyle(document.body).pointerEvents !== "none");
}

// Runs in the page.
function read_controls() {
	const visible = (el) => {
		const box = el.getBoundingClientRect();
		const style = getComputedStyle(el);
		return (
			box.width > 0 &&
			box.height > 0 &&
			style.visibility !== "hidden" &&
			!el.closest("[inert], [aria-hidden=true]")
		);
	};
	// What a screen reader reads from the content: text and image labels, not what `aria-hidden` hides.
	const text_of = (node) => {
		if (node.nodeType === Node.TEXT_NODE) return node.data;
		if (node.nodeType !== Node.ELEMENT_NODE || node.getAttribute("aria-hidden") === "true")
			return "";
		if (node.tagName === "IMG") return node.getAttribute("alt") || "";
		return [...node.childNodes].map(text_of).join(" ");
	};
	const name_of = (el) => {
		const labelled = el.getAttribute("aria-labelledby");
		const text = labelled
			? labelled
					.split(" ")
					.map((id) => document.getElementById(id)?.textContent)
					.join(" ")
			: el.getAttribute("aria-label") || text_of(el) || el.getAttribute("title") || "";
		return text.replace(/\s+/g, " ").trim();
	};
	// A field's own widgets (rich-text toolbar, pickers) are data entry: `record.set_values` covers them.
	const skipped = (el) => el.closest("[data-fieldname], [data-sonner-toast], [role=status]");
	const act_of = (el) =>
		(el.closest("[data-act]") || el.querySelector("[data-act]"))?.dataset.act || "";
	return [...document.querySelectorAll("button, [role=menuitem]")]
		.filter((el) => visible(el) && !skipped(el))
		.map((el) => ({
			name: name_of(el),
			act: act_of(el),
			view: !!(el.closest("[data-view]") || el.querySelector("[data-view]")),
			disabled: el.disabled || el.getAttribute("aria-disabled") === "true",
		}));
}

// A problem passes only when `gaps` lists its control, under the page's kind or one it `inherits` (a list page
// shares the list's controls). A gap of the page's own kind that no problem matches is stale: delete it.
export function judge(kind, problems, gaps, inherits = []) {
	const own = new Set(gaps[kind] || []);
	const listed = new Set([...own, ...inherits.flatMap((other) => gaps[other] || [])]);
	const seen = new Set(problems.map((p) => p.control));
	// Each scan reads the whole page, so one control comes back many times: report it once.
	const fresh = [...new Map(problems.map((p) => [p.control, p])).values()].filter(
		(p) => !listed.has(p.control)
	);
	const stale = [...own].filter((control) => !seen.has(control));
	return { fresh, stale };
}
