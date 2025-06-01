<script setup>
import Properties from "./Properties.vue";
import { ref } from "vue";

let sidebar_width = ref(272);
let sidebar_resizing = ref(false);

function start_resize() {
	$(document).on("mousemove", resize);
	$(document).on("mouseup", () => {
		$(".main").removeClass("resizing");
		sidebar_resizing.value = false;
		$(document).off("mousemove", resize);
	});
}

function resize(e) {
	sidebar_resizing.value = true;
	$(".main").addClass("resizing");
	sidebar_width.value = e.clientX - 90;

	if (sidebar_width.value < 16 * 16) {
		sidebar_width.value = 16 * 16;
	}
	if (sidebar_width.value > 24 * 16) {
		sidebar_width.value = 24 * 16;
	}
}
</script>

<template>
	<div
		:class="['sidebar-resizer', sidebar_resizing ? 'resizing' : '']"
		@mousedown="start_resize"
	></div>
	<div :style="{ width: `${sidebar_width}px` }">
		<Properties />
	</div>
</template>

<style lang="scss" scoped>
.sidebar-resizer {
	position: absolute;
	top: 0;
	right: -6px;
	width: 5px;
	height: 100%;
	opacity: 0;
	background-color: var(--bg-gray);
	transition: opacity 0.2s ease;
	z-index: 10;
	cursor: col-resize;

	&:hover,
	&.resizing {
		opacity: 1;
	}
}
</style>
