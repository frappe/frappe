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

	it("reads the counters once a new DocType's first save ends pending", async () => {
		const saving = reactive({ doctype: "ToDo", mode: "design", settings: { pending: true } });
		const scope = effectScope();
		const counters = scope.run(() => useSeriesCounters(saving as unknown as SettingsView, () => ["NOTE-.#####"]))!;
		await vi.advanceTimersByTimeAsync(300);
		expect(call).not.toHaveBeenCalled();
		saving.settings.pending = false;
		await nextTick();
		await vi.advanceTimersByTimeAsync(300);
		expect(counters.value).toEqual({ "NOTE-": 25 });
		scope.stop();
	});

	it("reads nothing for a DocType not yet saved, or a pattern without a key", async () => {
		expect(await countersOf(["NOTE-.#####"], true)).toEqual({});
		expect(await countersOf(["format:{customer}-.###"])).toEqual({});
		expect(call).not.toHaveBeenCalled();
	});
});
