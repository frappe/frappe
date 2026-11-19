// The Records group: one search per palette context, and a record's address where the router has no record route.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import type { PaletteContext } from "../paletteGroups";
import { records } from "../paletteRecords";

const fake = vi.hoisted(() => ({ runMethod: vi.fn() }));

vi.mock("@framework/ui/api", async (original) => ({
	...(await original<object>()),
	runMethod: fake.runMethod,
}));

const DESK = "/apps/desk";

function found(txt: string) {
	return [{ doctype: "ToDo", name: `${txt}-1`, label: `${txt} one`, route: `${DESK}/todo/${txt}-1` }];
}

/** A context like the index's: its router holds `home` only. */
function indexContext(): PaletteContext {
	return {
		boot: { app: null, shell_base: "/apps" } as unknown as Boot,
		router: createRouter({ history: createMemoryHistory(), routes: [{ path: "/", name: "home", component: {} }] }),
		addresses: new Addresses({ doctypes: {}, modules: {}, singles: [] }),
	};
}

function labels(context: PaletteContext) {
	return records.rows("", context).map((row) => row.label);
}

beforeEach(() => {
	fake.runMethod.mockReset().mockImplementation(async (_method: string, args: { txt: string }) => ({
		data: found(args.txt),
	}));
});

describe("the palette's Records group", () => {
	it("opens a record at the address the server gives where the router has no record route", async () => {
		const context = indexContext();
		records.follow!("kestrel", context);
		await vi.waitFor(() => expect(labels(context)).toEqual(["kestrel one"]));
		expect(records.rows("", context)[0].href).toBe(`${DESK}/todo/kestrel-1`);
	});

	it("keeps one search per context, so one query never clears another's", async () => {
		const index = indexContext();
		const palette = indexContext();
		records.follow!("kestrel", index);
		await vi.waitFor(() => expect(labels(index)).toEqual(["kestrel one"]));

		records.follow!("osprey", palette);
		await vi.waitFor(() => expect(labels(palette)).toEqual(["osprey one"]));
		records.follow!("", palette);
		expect(labels(palette)).toEqual([]);
		expect(labels(index)).toEqual(["kestrel one"]);
	});
});
