// The quick actions row's fit: labels go first, then whole items, measured against the row.
import { describe, expect, it } from "vitest";
import { nextTick, ref } from "vue";
import { useFittedActions } from "../fittedActions";

// A row whose width follows the fit: each label is 40 wide, each icon 20, until it fits `room`.
function rowFor(room: number, counts: { labelled: () => number; visible: () => number }) {
	return {
		get clientWidth() {
			return room;
		},
		get scrollWidth() {
			return counts.labelled() * 40 + (counts.visible() - counts.labelled()) * 20;
		},
	} as unknown as HTMLElement;
}

async function settle() {
	for (let i = 0; i < 12; i++) await nextTick();
}

describe("useFittedActions", () => {
	it("names every item when the row has room", async () => {
		const total = ref(3);
		const row = ref<HTMLElement | null>(null);
		const fit = useFittedActions(row, () => total.value, () => true);
		row.value = rowFor(200, { labelled: () => fit.labelled.value, visible: () => fit.visible.value });
		await settle();
		expect([fit.labelled.value, fit.visible.value]).toEqual([3, 3]);
	});

	it("drops labels from the right before it hides anything", async () => {
		const total = ref(3);
		const row = ref<HTMLElement | null>(null);
		const fit = useFittedActions(row, () => total.value, () => true);
		row.value = rowFor(85, { labelled: () => fit.labelled.value, visible: () => fit.visible.value });
		await settle();
		// 40 + 20 + 20 = 80 fits; 40 + 40 + 20 does not.
		expect([fit.labelled.value, fit.visible.value]).toEqual([1, 3]);
	});

	it("hides trailing items once no label is left to drop, keeping one", async () => {
		const total = ref(4);
		const row = ref<HTMLElement | null>(null);
		const fit = useFittedActions(row, () => total.value, () => true);
		row.value = rowFor(75, { labelled: () => fit.labelled.value, visible: () => fit.visible.value });
		await settle();
		// One label and two icons is 80; one label and one icon is 60.
		expect([fit.labelled.value, fit.visible.value]).toEqual([1, 2]);
		total.value = 1;
		await settle();
		expect([fit.labelled.value, fit.visible.value]).toEqual([1, 1]);
	});

	it("names nothing and hides nothing when not fitting", async () => {
		const row = ref<HTMLElement | null>(null);
		const fit = useFittedActions(row, () => 5, () => false);
		row.value = rowFor(10, { labelled: () => 0, visible: () => 5 });
		await settle();
		expect([fit.labelled.value, fit.visible.value]).toEqual([0, 5]);
	});
});
