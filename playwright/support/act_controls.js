// The act-control check: every visible button and menu item on a desk v2 page names an act the page can run
// (`data-act`) or says it only changes the view (`data-view`), and every button has an accessible name.
import fs from "fs";
import path from "path";

const GAPS = path.join(__dirname, "../../frontend/act-gaps.json");

export function read_gaps() {
	return JSON.parse(fs.readFileSync(GAPS, "utf8"));
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
	const name_of = (el) => {
		const labelled = el.getAttribute("aria-labelledby");
		const text = labelled
			? labelled
					.split(" ")
					.map((id) => document.getElementById(id)?.textContent)
					.join(" ")
			: el.getAttribute("aria-label") || el.textContent || el.getAttribute("title") || "";
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

// A problem passes only when `gaps` lists its control. A gap that no problem matches is stale: delete it.
export function judge(kind, problems, gaps) {
	const listed = new Set(gaps[kind] || []);
	const seen = new Set(problems.map((p) => p.control));
	const fresh = problems.filter((p) => !listed.has(p.control));
	const stale = [...listed].filter((control) => !seen.has(control));
	return { fresh, stale };
}
