// The layout source as something a load can await: now when idle, later when a fetch is in flight.
import { describe, expect, it } from "vitest";
import { nextTick, ref } from "vue";
import { whenSettled } from "../formLayoutSource/useFormLayout";

describe("whenSettled", () => {
	it("answers now when nothing is loading", async () => {
		await expect(whenSettled(ref(false))).resolves.toBeUndefined();
	});

	it("waits for the flag to drop, once", async () => {
		const loading = ref(true);
		let done = false;
		const settled = whenSettled(loading).then(() => (done = true));
		await nextTick();
		expect(done).toBe(false);
		loading.value = false;
		await nextTick();
		await settled;
		expect(done).toBe(true);
	});
});
