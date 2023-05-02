import { defineStore } from "pinia";
import { ref } from "vue";

export const useStore = defineStore("workflow-builder-store", () => {
	let workflow = ref({
		elements: [
			{ id: "1", label: "Open", type: "state", position: { x: 300, y: 150 } },
			{ id: "2", label: "Approved", type: "state", position: { x: 700, y: 150 } },
			{
				id: "edge-1-2",
				source: "1",
				target: "2",
				type: "transition",
				sourceHandle: "b",
				targetHandle: "d",
				animated: true,
			},
		],
	});

	return {
		workflow,
	};
});
