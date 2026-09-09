// The history entry's memory: written over the router's own state, read back after a pop.
import { beforeEach, describe, expect, it } from "vitest";

import {
	readListMemory,
	recallRows,
	rememberRows,
	rememberScroll,
	writeListMemory,
} from "../pageState";

beforeEach(() => {
	history.replaceState({ position: 3, current: "/lead" }, "");
});

describe("the list memory", () => {
	it("is empty on an entry nothing wrote", () => {
		expect(readListMemory()).toEqual({});
	});

	it("keeps the router's keys and merges its own", () => {
		writeListMemory({ pageSize: 100 });
		writeListMemory({ scrollTop: 240 });
		expect(readListMemory()).toEqual({ pageSize: 100, scrollTop: 240 });
		expect(history.state).toMatchObject({ position: 3, current: "/lead" });
	});

	it("does not follow a pushed entry", () => {
		writeListMemory({ pageSize: 500 });
		history.pushState({ position: 4 }, "", "/lead/LEAD-1");
		expect(readListMemory()).toEqual({});
	});
});

describe("the rows memory", () => {
	it("answers for the same doctype and query only, with the last write", () => {
		rememberRows("Lead", { query: "a", pageSize: 20, shown: 40 });
		rememberRows("Lead", { query: "a", pageSize: 100, shown: 200 });
		expect(recallRows("Lead", "a")).toEqual({ query: "a", pageSize: 100, shown: 200 });
		expect(recallRows("Lead", "b")).toBeUndefined();
		expect(recallRows("Deal", "a")).toBeUndefined();
	});

	it("keeps the scroll offset for the same query through a rows write, and drops it for a new one", () => {
		rememberRows("Lead", { query: "a", pageSize: 20, shown: 20 });
		rememberScroll("Lead", "a", 240);
		rememberRows("Lead", { query: "a", pageSize: 20, shown: 40 });
		expect(recallRows("Lead", "a")).toMatchObject({ shown: 40, scrollTop: 240 });
		rememberScroll("Lead", "b", 999);
		expect(recallRows("Lead", "a")?.scrollTop).toBe(240);
		rememberRows("Lead", { query: "b", pageSize: 20, shown: 20 });
		expect(recallRows("Lead", "b")?.scrollTop).toBeUndefined();
	});
});
