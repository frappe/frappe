// The next-name previews read each series key's counter from the site.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, reactive } from "vue";

const { call } = vi.hoisted(() => ({ call: vi.fn() }));
vi.mock("@framework/ui/api", () => ({ runMethod: call }));

import { useSeriesCounters } from "../seriesCounters";
import type { SettingsView } from "../settingsView";

const view = (pending = false) => ({ doctype: "ToDo", mode: "design", settings: { pending } }) as unknown as SettingsView;

async function countersOf(patterns: string[], pending = false) {
	const scope = effectScope();
	const counters = scope.run(() => useSeriesCounters(view(pending), () => patterns))!;
	await vi.advanceTimersByTimeAsync(300);
	await nextTick();
	scope.stop();
	return counters.value;
}

describe("the series counters", () => {
	beforeEach(() => {
		vi.useFakeTimers();
		call.mockReset();
		call.mockImplementation(async (_method, args) => ({
			data: Object.fromEntries(JSON.parse(args.prefixes).map((prefix: string) => [prefix, 25])),
		}));
	});
	afterEach(() => vi.useRealTimers());

	it("reads the empty key a format pattern's braced counter counts under", async () => {
		expect(await countersOf(["format:WS-{YYYY}-{#####}"])).toEqual({ "": 25 });
		expect(JSON.parse(call.mock.calls[0][1].prefixes)).toEqual([""]);
	});

	it("reads each dot series key once", async () => {
		const year = new Date().getFullYear();
		expect(await countersOf(["TN-.YYYY.-.####", "TN-.YYYY.-.####"])).toEqual({ [`TN-${year}-`]: 25 });
		expect(call).toHaveBeenCalledTimes(1);
	});

	it("reads a new DocType's counters before its first save: a key may count another DocType's records", async () => {
		expect(await countersOf(["format:WI-{#####}"], true)).toEqual({ "": 25 });
	});

	it("reads nothing for a pattern without a key", async () => {
		expect(await countersOf(["format:{customer}-.###"])).toEqual({});
		expect(call).not.toHaveBeenCalled();
	});
});
