import { defineStore } from "pinia";
import { useMainStore } from "./MainStore";
import {
	createText,
	createRectangle,
	createDynamicText,
	createImage,
	createTable,
} from "../defaultObjects";
export const useElementStore = defineStore("ElementStore", {
	state: () => ({
		Elements: new Array(),
	}),
	actions: {
		createNewObject(event, element) {
			let newElement;
			const MainStore = useMainStore();
			if (MainStore.activeControl == "text") {
				if (MainStore.textControlType == "static") {
					newElement = createText(event, element);
				} else {
					newElement = createDynamicText(event, element);
				}
			} else if (MainStore.activeControl == "rectangle") {
				newElement = createRectangle(event, element);
			} else if (MainStore.activeControl == "image") {
				newElement = createImage(event, element);
			} else if (MainStore.activeControl == "table") {
				newElement = createTable(event, element);
			}
			return newElement;
		},
	},
});
