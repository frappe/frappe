import { defineStore } from "pinia";
import { ref } from "vue";

export const useStore = defineStore("workflow-builder-store", () => {
	let workflow = ref({
		elements: [],
	});

	return {
		workflow,
	};
});
