// The editor page's one answer to "a slow load must not land after a later one".
import { expect, it } from "vitest";
import { LatestWins } from "../latestWins";

it("ends a request when a later one begins", () => {
	const loads = new LatestWins();
	const slow = loads.begin();
	const fast = loads.begin();
	expect([slow(), fast()]).toEqual([false, true]);
});

it("ends every request and watch on cancel", () => {
	const loads = new LatestWins();
	const request = loads.begin();
	const watch = loads.watch();
	loads.cancel();
	expect([request(), watch()]).toEqual([false, false]);
	expect(loads.begin()()).toBe(true);
});

it("keeps a watch through a later begin", () => {
	const loads = new LatestWins();
	const watch = loads.watch();
	loads.begin();
	expect(watch()).toBe(true);
});

it("ends every request, now and later, on stop", () => {
	const loads = new LatestWins();
	const request = loads.begin();
	loads.stop();
	expect([request(), loads.begin()(), loads.watch()(), loads.isStopped]).toEqual([false, false, false, true]);
});
