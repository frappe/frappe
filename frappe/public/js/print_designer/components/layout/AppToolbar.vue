<template>
	<div class="sidebar">
		<div class="toolbar-section mt-3">
			<div>
				<span
					v-for="({ id, aria_label, icon }, key) in MainStore.controls"
					:key="id"
					:title="aria_label"
					:class="iconClasses(id, icon)"
					@click="MainStore.setActiveControl(key)"
				></span>
			</div>
			<LayersIcon />
		</div>
		<LayersPanel v-if="MainStore.isLayerPanelEnabled" />
	</div>
</template>

<script setup>
import { watch } from "vue";
import LayersIcon from "../../icons/LayersIcon.vue";
import { useMainStore } from "../../store/MainStore";
import LayersPanel from "./LayersPanel.vue";
const MainStore = useMainStore();

const iconClasses = (id, icon) => [
	icon,
	"tool-icons",
	{ "active-tool-icon": MainStore.activeControl == id },
];

watch(
	() => MainStore.activeControl,
	() => {
		if (
			MainStore.activeControl == "text" &&
			(document.activeElement.getAttribute("contenteditable") == null || false) &&
			!MainStore.getCurrentElementsValues.includes(document.activeElement)
		) {
			MainStore.currentElements = {};
		} else if (MainStore.activeControl == "rectangle") {
			MainStore.currentElements = {};
		}
	}
);

MainStore.$subscribe((mutation, state) => {
	if (mutation.events.key == "isLayerPanelEnabled") {
		if (mutation.events.newValue) {
			MainStore.toolbarWidth = 244;
		} else {
			MainStore.toolbarWidth = 44;
		}
	}
});
</script>

<style scoped>
.sidebar {
	display: flex;
}
.toolbar-section {
	display: flex;
	flex-direction: column;
	justify-content: space-between;
}
.tool-icons {
	text-align: center;
	user-select: none;
	width: 44px;
	height: 44px;
}

.active-tool-icon {
	color: var(--primary);
}
</style>
