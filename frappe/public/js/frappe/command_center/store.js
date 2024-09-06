import { defineStore } from "pinia";

export const useCommandCenterStore = defineStore({
	id: "command-center",
	state: () => ({
		dialog: null,
		currentAction: null,
	}),
});
