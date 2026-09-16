// A saved Client Script re-runs the page on screen, unless the reader is mid-edit.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import { invalidateClientScripts, resetClientScripts } from "@/recordPage/clientScripts";
import { useLiveClientScripts } from "../liveClientScripts";

function setup(doctype: string | null = "CRM Deal") {
	const target = ref<string | null>(doctype);
	const refresh = vi.fn(() => Promise.resolve());
	let dirty = false;
	const stop = useLiveClientScripts({ doctype: target, dirty: () => dirty, refresh });
	return { target, refresh, stop, edit: () => void (dirty = true) };
}

describe("useLiveClientScripts", () => {
	beforeEach(() => resetClientScripts());

	it("re-runs a clean page when its doctype's scripts change", async () => {
		const { refresh } = setup();
		invalidateClientScripts("CRM Deal");
		await nextTick();
		expect(refresh).toHaveBeenCalledTimes(1);
	});

	it("leaves a page with unsaved edits alone", async () => {
		const { refresh, edit } = setup();
		edit();
		invalidateClientScripts("CRM Deal");
		await nextTick();
		expect(refresh).not.toHaveBeenCalled();
	});

	it("ignores another doctype's change", async () => {
		const { refresh } = setup();
		invalidateClientScripts("CRM Lead");
		await nextTick();
		expect(refresh).not.toHaveBeenCalled();
	});

	it("does not re-run on a route change, even onto a doctype that changed earlier", async () => {
		const { target, refresh } = setup();
		invalidateClientScripts("CRM Lead");
		target.value = "CRM Lead";
		await nextTick();
		expect(refresh).not.toHaveBeenCalled();
	});

	it("re-runs once more on a second change of the same doctype", async () => {
		const { refresh } = setup();
		invalidateClientScripts("CRM Deal");
		await nextTick();
		invalidateClientScripts("CRM Deal");
		await nextTick();
		expect(refresh).toHaveBeenCalledTimes(2);
	});

	it("does not re-run when a reset drops the count to zero", async () => {
		const { refresh } = setup();
		invalidateClientScripts("CRM Deal");
		await nextTick();
		resetClientScripts();
		await nextTick();
		expect(refresh).toHaveBeenCalledTimes(1);
	});

	it("tolerates a page that is not built yet", async () => {
		const target = ref<string | null>("CRM Deal");
		const refresh = vi.fn(() => undefined);
		useLiveClientScripts({ doctype: target, dirty: () => false, refresh });
		invalidateClientScripts("CRM Deal");
		await nextTick();
		expect(refresh).toHaveBeenCalledTimes(1);
	});

	it("keeps a failed re-run quiet", async () => {
		const target = ref<string | null>("CRM Deal");
		const refresh = vi.fn(() => Promise.reject(new Error("boom")));
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		useLiveClientScripts({ doctype: target, dirty: () => false, refresh });
		invalidateClientScripts("CRM Deal");
		await nextTick();
		await Promise.resolve();
		expect(refresh).toHaveBeenCalledTimes(1);
		expect(warn).toHaveBeenCalledTimes(1);
		warn.mockRestore();
	});
});
