<template>
	<AppHeader :appIcon="appIcon" :print_format_name="print_format_name" />
	<div class="main-layout" id="main-layout">
		<AppToolbar :class="toolbarClasses" />
		<AppCanvas class="app-sections print-format-container" />
		<PropertiesPanel class="app-sections properties-panel" />
	</div>
</template>

<script setup>
import { computed, onMounted, watchEffect, watch } from "vue";
import { useMainStore } from "./store/MainStore";
import AppHeader from "./components/layout/AppHeader.vue";
import AppToolbar from "./components/layout/AppToolbar.vue";
import AppCanvas from "./components/layout/AppCanvas.vue";
import PropertiesPanel from "./components/layout/PropertiesPanel.vue";
import { useAttachKeyBindings } from "./composables/AttachKeyBindings";
import { pageSizes } from "./pageSizes";
import { fetchMeta } from "./store/fetchMetaAndData";

const props = defineProps({
	print_format_name: {
		type: String,
		required: true,
	},
	appIcon: {
		type: String,
		required: true,
	},
});
const MainStore = useMainStore();

const toolbarClasses = computed(() => {
	return [
		"app-sections",
		"toolbar",
		{ "toolbar-with-layer-panel": MainStore.isLayerPanelEnabled },
	];
});

useAttachKeyBindings();

window.addEventListener("resize", (e) => {
	if (!window.matchMedia("(min--moz-device-pixel-ratio: 0)").matches) {
		MainStore.browserZoomLevel = window.devicePixelRatio;
		MainStore.isRetina && (MainStore.browserZoomLevel /= 2);
		if (window.devicePixelRatio == 2 && MainStore.isRetina) {
			if (
				MainStore.browserZoomLevel !=
				parseFloat((window.outerWidth / window.innerWidth).toFixed(2))
			) {
				MainStore.browserZoomLevel = parseFloat(
					(window.outerWidth / window.innerWidth).toFixed(2)
				);
			}
		}
	}
});
window.visualViewport.addEventListener("resize", () => {
	if (!window.matchMedia("(min--moz-device-pixel-ratio: 0)").matches) {
		MainStore.browserZoomLevel = window.devicePixelRatio;
		MainStore.isRetina && (MainStore.browserZoomLevel /= 2);
		if (window.devicePixelRatio == 2 && MainStore.isRetina) {
			if (
				MainStore.browserZoomLevel !=
				parseFloat((window.outerWidth / window.innerWidth).toFixed(2))
			) {
				MainStore.browserZoomLevel = parseFloat(
					(window.outerWidth / window.innerWidth).toFixed(2)
				);
			}
		}
		MainStore.browserZoomLevel += window.visualViewport.scale - 1;
	} else {
		MainStore.browserZoomLevel = window.visualViewport.scale;
	}
});
onMounted(() => {
	MainStore.print_design_name = props.print_format_name;
	fetchMeta();
	const screen_stylesheet = document.createElement("style");
	screen_stylesheet.title = "print-designer-stylesheet";
	screen_stylesheet.rel = "stylesheet";
	document.head.appendChild(screen_stylesheet);
	MainStore.bodyElement = document.getElementById("body");

	const print_stylesheet = document.createElement("style");
	print_stylesheet.title = "page-print-designer-stylesheet";
	print_stylesheet.rel = "stylesheet";
	print_stylesheet.media = "page";
	document.head.appendChild(print_stylesheet);
	for (let i = document.styleSheets.length - 1; i >= 0; i--) {
		if (document.styleSheets[i].title == "print-designer-stylesheet") {
			MainStore.screenStyleSheet = document.styleSheets[i];
		} else if (document.styleSheets[i].title == "page-print-designer-stylesheet") {
			MainStore.printStyleSheet = document.styleSheets[i];
		}
	}
	MainStore.bodyElement = document.getElementById("body");

	MainStore.pageSizes = pageSizes["ISO paper sizes"];
});
watchEffect(() => {
	if (MainStore.activeControl == "mouse-pointer") {
		MainStore.isMarqueeActive = true;
		MainStore.isDrawing = false;
	} else if (["rectangle", "image"].includes(MainStore.activeControl)) {
		MainStore.isMarqueeActive = false;
		MainStore.isDrawing = true;
	} else {
		MainStore.isMarqueeActive = false;
		MainStore.isDrawing = false;
	}
});
</script>
<style scoped lang="scss">
.main-layout {
	display: flex;
	justify-content: space-between;
	margin: 0;

	.app-sections {
		flex: 1;
		height: calc(100vh - 61px);
		padding: 0;
		margin-top: 0;
		background-color: var(--card-bg);
		box-shadow: var(--card-shadow);
	}

	.toolbar {
		z-index: 1;
		width: 44px;
		max-width: 44px;
	}
	.toolbar-with-layer-panel {
		width: 244px;
		max-width: 244px;
		box-shadow: unset;
	}
	.print-format-container {
		overflow: auto;
		display: flex;
		position: relative;
		flex-direction: column;
		height: calc(100vh - 61px);
		background-color: #f2f3f3;
	}
	.properties-panel {
		width: 250px;
		max-width: 250px;
	}
}
</style>
