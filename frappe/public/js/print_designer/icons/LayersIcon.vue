<template>
	<svg
		class="layers-icon"
		@click="MainStore.isLayerPanelEnabled = !MainStore.isLayerPanelEnabled"
		title="Layers Panel"
		width="18"
		height="18"
		viewBox="0 0 68 69"
		fill="none"
		xmlns="http://www.w3.org/2000/svg"
	>
		<path
			d="M63.8224 39.2915L37.8752 21.8593C36.1994 20.7334 34.0109 20.7258 32.3274 21.84L4.30253 40.3871C1.31456 42.3645 1.31528 46.7507 4.3039 48.7271L30.6662 66.1615C32.3497 67.2748 34.5374 67.2669 36.2127 66.1414L63.8224 47.5922C66.7713 45.611 66.7713 41.2727 63.8224 39.2915Z"
			:fill="fillColor"
			stroke="white"
			stroke-width="5"
		/>
		<path
			d="M63.8224 20.2915L37.8752 2.85926C36.1994 1.73341 34.0109 1.72581 32.3274 2.84L4.30252 21.3871C1.31455 23.3645 1.31527 27.7506 4.30389 29.7271L30.6662 47.1615C32.3496 48.2748 34.5373 48.2669 36.2126 47.1413L63.8224 28.5922C66.7713 26.611 66.7713 22.2727 63.8224 20.2915Z"
			:fill="fillColor"
			stroke="white"
			stroke-width="5"
		/>
	</svg>
</template>

<script setup>
import { useMainStore } from "../store/MainStore";
import { ref } from "vue";

const MainStore = useMainStore();
const fillColor = ref("var(--text-light)");

MainStore.$subscribe((mutations, state) => {
	if (mutations.events.key != "toolbarWidth") return;
	if (mutations.events.newValue > 44) {
		fillColor.value = "var(--primary-color)";
	} else {
		fillColor.value = "var(--text-light)";
	}
});
</script>

<style scoped>
.layers-icon {
	user-select: none;
	margin: 0px auto;
	margin-bottom: 15px;
}
</style>
