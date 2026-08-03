<template>
	<div
		class="pfb-radius-handle"
		:class="{ active }"
		:style="pos"
		:title="__('Drag to change corner radius')"
		@pointerdown.stop.prevent="start"
	>
		<span v-if="active" class="pfb-radius-tip">{{ radius }}</span>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { canvas_zoom } from "../../utils";

const props = defineProps(["section"]);
const active = ref(false);

const radius = computed(() => props.section.radius || 0);
// sits on the rounded corner arc (top-left), never closer than a grabbable gap
const pos = computed(() => {
	const r = Math.max(radius.value, 10) + "px";
	return { top: r, left: r };
});

function start(e) {
	active.value = true;
	const zoom = canvas_zoom(e.currentTarget);
	const ox = e.clientX;
	const oy = e.clientY;
	const start_val = radius.value;

	function move(ev) {
		// dragging toward the section centre (down-right) grows the radius
		const delta = (ev.clientX - ox + (ev.clientY - oy)) / 2 / zoom;
		props.section.radius = Math.max(0, Math.round(start_val + delta));
	}
	function up() {
		active.value = false;
		window.removeEventListener("pointermove", move);
		window.removeEventListener("pointerup", up);
	}
	window.addEventListener("pointermove", move);
	window.addEventListener("pointerup", up);
}
</script>

<style scoped>
.pfb-radius-handle {
	position: absolute;
	width: 12px;
	height: 12px;
	transform: translate(-50%, -50%);
	border-radius: 50%;
	background: var(--fg-color);
	border: 2px solid var(--pfb-accent);
	box-shadow: var(--shadow-sm);
	cursor: nwse-resize;
	pointer-events: auto;
	z-index: 4;
}

.pfb-radius-tip {
	position: absolute;
	left: 14px;
	top: 50%;
	transform: translateY(-50%);
	background: var(--pfb-accent);
	color: #fff;
	font-size: var(--text-tiny);
	line-height: 1;
	padding: 2px 5px;
	border-radius: var(--radius-sm);
	white-space: nowrap;
	pointer-events: none;
}
</style>
