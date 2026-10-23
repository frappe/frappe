// Which Flow Run a transcript turn belongs to. The log's runs and the session's Flow Run
// rows are created in the same order; a run resumed after an approval pause continues
// its row, so the resumed segment joins the span of the run it continues. Synced rows
// name their latest segment (daemon_run_id), which pins the match exactly. A synced row
// no span names was rewound off the branch, so only unsynced rows are matched by order.
export function runSpans(rows) {
	const spans = [];
	let resumable = false;
	for (const row of rows) {
		if (row.type === "run_started") {
			if (resumable && spans.length) {
				spans[spans.length - 1].runIds.push(row.run_id);
				spans[spans.length - 1].endSeq = null;
			} else spans.push({ startSeq: row.seq, endSeq: null, runIds: [row.run_id] });
			resumable = false;
		} else if (row.type === "run_ended") {
			const span = spans[spans.length - 1];
			if (span) span.endSeq = row.seq;
			resumable = row.reason === "paused";
		} else if (typeof row.seq === "number" && row.type !== "model_changed") {
			// anything else logged while paused (a cancelled batch's results) means the next
			// run starts afresh; a model change leaves the batch waiting
			resumable = false;
		}
	}
	return spans;
}

export function matchRuns(spans, runs) {
	const byId = new Map();
	for (const run of runs) if (run.daemon_run_id) byId.set(run.daemon_run_id, run);
	const matched = spans.map(
		(span) => span.runIds.map((id) => byId.get(id)).find(Boolean) ?? null
	);
	const taken = new Set(matched.filter(Boolean).map((run) => run.name));
	const spare = runs.filter((run) => !taken.has(run.name) && !run.daemon_run_id);
	let next = 0;
	return matched.map((run) => run ?? spare[next++] ?? null);
}

// Index once per session update, shared by every turn's feedback control.
export function runsByUserMessage(rows, runs) {
	const spans = runSpans(rows);
	const matched = matchRuns(spans, runs);
	const result = new Map();
	let index = 0;
	for (const row of rows) {
		if (row.type !== "user_message") continue;
		while (index + 1 < spans.length && spans[index + 1].startSeq <= row.seq) index++;
		const span = spans[index];
		if (span && span.startSeq <= row.seq && (span.endSeq == null || row.seq <= span.endSeq))
			result.set(row.seq, matched[index]);
	}
	return result;
}
