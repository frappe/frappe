// The meta as a promise: settled now on a cached doctype, later on a fresh one.
import { describe, expect, it } from "vitest";
import { nextTick, ref } from "vue";
import { awaitMeta } from "../metaSource";

describe("awaitMeta", () => {
	it("answers a meta the source already holds, as a second visit to the doctype finds it", async () => {
		const meta = { name: "CRM Deal" };
		await expect(awaitMeta({ meta: ref(meta), error: ref(null) })).resolves.toEqual(meta);
	});

	it("waits for a meta still loading, and stops watching once it lands", async () => {
		const source = { meta: ref<any>(null), error: ref<unknown>(null) };
		const settled = awaitMeta(source);
		source.meta.value = { name: "CRM Deal" };
		await nextTick();
		await expect(settled).resolves.toEqual({ name: "CRM Deal" });
	});

	it("waits out a stale meta and answers the fresh one", async () => {
		const source = { meta: ref<any>({ name: "CRM Deal", version: 1 }), error: ref(null), refreshing: ref(true) };
		let answered: any = null;
		void awaitMeta(source).then((meta) => (answered = meta));
		await nextTick();
		expect(answered).toBeNull();

		source.meta.value = { name: "CRM Deal", version: 2 };
		source.refreshing.value = false;
		await nextTick();
		await Promise.resolve();
		expect(answered).toEqual({ name: "CRM Deal", version: 2 });
	});

	it("rejects when the fresh read of a stale meta fails, though the stale meta stays on show", async () => {
		const stale = { name: "CRM Deal", version: 1 };
		const source = { meta: ref<any>(stale), error: ref(null), refreshing: ref(true), refreshError: ref<unknown>(null) };
		const settled = awaitMeta(source);
		source.refreshError.value = new Error("Network down");
		source.refreshing.value = false;
		await nextTick();
		await expect(settled).rejects.toThrow("Network down");
		expect(source.meta.value).toEqual(stale);
	});

	it("rejects with the source's error, now or later", async () => {
		await expect(awaitMeta({ meta: ref(null), error: ref(new Error("gone")) })).rejects.toThrow("gone");
		const source = { meta: ref<any>(null), error: ref<unknown>(null) };
		const settled = awaitMeta(source);
		source.error.value = new Error("later");
		await nextTick();
		await expect(settled).rejects.toThrow("later");
	});
});
