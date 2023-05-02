import { defineStore } from "pinia";
import { ref } from "vue";

export const useStore = defineStore("workflow-builder-store", () => {
	let workflow = ref({
		elements: [
			{ id: "1", label: "Open", type: "state", position: { x: 300, y: 150 } },
			{ id: "2", label: "Approved", type: "state", position: { x: 700, y: 150 } },
			{ id: "action-1", label: "Approve", type: "action", position: { x: 500, y: 170 } },
			{
				id: "edge-1-action-1",
				source: "1",
				target: "action-1",
				type: "transition",
				sourceHandle: "right",
				targetHandle: "left",
				updatable: true,
				animated: true,
			},
			{
				id: "edge-action-1-2",
				source: "action-1",
				target: "2",
				type: "transition",
				sourceHandle: "right",
				targetHandle: "left",
				updatable: true,
				animated: true,
			},
		],
	});

	return {
		workflow,
	};
});
