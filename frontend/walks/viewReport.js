// Prints one network's run of the view-restore walk as a table, with a note under each failure.

const COLUMNS = ["step", "details", "panel", "tab", "sections", "framesOff", "ms", "pass"];

export function printRun(target, layout, run) {
	const via = `list reached from the ${run.listVia ?? "-"}, record from the ${
		run.recordVia ?? "-"
	}`;
	write(`\n${run.network} network, ${target.doctype}, ${via}`);
	write(`first visit: form tab "${layout.tab}", section "${layout.section}" opened`);
	if (run.steps.some((step) => step.view?.panelMarked === false))
		write("the panel column has no data-body-scroll mark; its first child was read instead");
	printLine(COLUMNS);
	for (const step of run.steps) {
		printLine(cells(step));
		for (const note of notes(step)) write(`${"".padEnd(20)}${note}`);
	}
	if (run.steps.some((step) => step.unproven))
		write(
			"rule 7 unproven: the site has no Record navigation item kind, so record-via-nav " +
				"clicked the list row, not the same record on the rail; the run fails"
		);
	if (run.error) write(`stopped: ${run.error}`);
	if (run.pageError) write(`first page error: ${run.pageError}`);
}

function cells(step) {
	const [details, panel] = step.offsets ?? [];
	const framesOff = step.offsets?.map((offset) => offset.framesOff ?? "-").join("/");
	return [
		step.step,
		details ? offsetCell(details) : "-",
		panel ? offsetCell(panel) : "-",
		step.tabOk === undefined ? "-" : yesNo(step.tabOk),
		step.sectionsOk === undefined ? "-" : yesNo(step.sectionsOk),
		framesOff ?? "-",
		step.settled ? step.ms : `>${step.ms}`,
		step.pass === undefined ? "-" : yesNo(step.pass),
	];
}

function notes(step) {
	if (step.pass !== false) return [];
	const lines = [];
	for (const offset of step.offsets) {
		if (!offset.ok) lines.push(`${offset.name} at ${offset.got} px, wanted ${offset.want} px`);
		if (offset.framesOff)
			lines.push(
				`${offset.name}: ${offset.framesOff} of ${
					step.frameCount
				} frames showed another offset, first ${shownOffset(offset.firstOff)}`
			);
	}
	if (step.tabOk === false) lines.push(`form tab "${step.view.tab}"`);
	for (const section of step.sectionsOff ?? []) lines.push(`section ${section}`);
	if (!step.settled) lines.push("did not settle in time");
	return lines;
}

function shownOffset(value) {
	return value === null ? "no scroller shown" : `${value} px`;
}

function offsetCell({ got, want }) {
	return got === want ? `${got}` : `${got}/${want}`;
}

function yesNo(value) {
	return value ? "yes" : "NO";
}

function printLine(line) {
	write(line.map((cell, index) => String(cell).padEnd(index ? 11 : 20)).join(""));
}

function write(text) {
	process.stdout.write(`${text}\n`);
}
