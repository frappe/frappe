import fs from "node:fs";
import path from "node:path";
import { SourceMapConsumer } from "source-map-js";

const OUT_DIR = process.env.UI_IMPACT_MAP_DIR;
const APP_SOURCE = /(?:^|\/)(frappe\/public\/[^?]+)/;

const consumers = new Map();
const impact = new Map();

export async function start_coverage(page) {
	if (OUT_DIR) await page.coverage.startJSCoverage({ resetOnNavigation: false });
}

export async function stop_coverage(page, spec_file) {
	if (!OUT_DIR) return;
	const spec = path.relative(process.cwd(), spec_file);
	for (const entry of await page.coverage.stopJSCoverage()) {
		const consumer = await source_map(entry);
		if (!consumer) continue;
		const line_starts = get_line_starts(entry.source);
		for (const fn of entry.functions) {
			const range = fn.ranges[0];
			if (!range.count || range.startOffset === 0) continue;
			const { source } = consumer.originalPositionFor(
				position(line_starts, range.startOffset)
			);
			const file = source && APP_SOURCE.exec(source)?.[1];
			if (file && !file.includes("/node_modules/")) {
				if (!impact.has(file)) impact.set(file, new Set());
				impact.get(file).add(spec);
			}
		}
	}
	write();
}

async function source_map(entry) {
	if (!entry.url.includes("/assets/") || !entry.source) return null;
	if (!consumers.has(entry.url)) {
		const name = /\/\/# sourceMappingURL=(\S+)\s*$/.exec(entry.source)?.[1];
		let consumer = null;
		if (name && !name.startsWith("data:")) {
			const res = await fetch(new URL(name, entry.url));
			if (res.ok) consumer = new SourceMapConsumer(await res.json());
		}
		consumers.set(entry.url, consumer);
	}
	return consumers.get(entry.url);
}

function get_line_starts(source) {
	const starts = [0];
	for (let i = source.indexOf("\n"); i !== -1; i = source.indexOf("\n", i + 1))
		starts.push(i + 1);
	return starts;
}

function position(line_starts, offset) {
	let low = 0;
	let high = line_starts.length - 1;
	while (low < high) {
		const mid = (low + high + 1) >> 1;
		if (line_starts[mid] <= offset) low = mid;
		else high = mid - 1;
	}
	return { line: low + 1, column: offset - line_starts[low] };
}

function write() {
	const map = {};
	for (const [file, specs] of impact) map[file] = [...specs].sort();
	fs.mkdirSync(OUT_DIR, { recursive: true });
	fs.writeFileSync(
		path.join(OUT_DIR, `ui-impact-map-${process.pid}.json`),
		JSON.stringify({ generated_at: new Date().toISOString(), map })
	);
}
