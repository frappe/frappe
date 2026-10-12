<template>
	<div
		class="pfb-radius-handle"
		:class="{ active }"
		:style="{ '--pfb-radius-inset': inset }"
		:title="__('Drag to change corner radius')"
		@pointerdown.stop.prevent="start"
	>
		<span v-if="active" class="pfb-radius-tip">{{ radius }}</span>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { canvas_zoom } from "../../utils";

const props = defineProps({
	target: { type: Object, required: true },
	prop: { type: String, default: "radius" },
});
const active = ref(false);

const radius = computed(() => props.target[props.prop] || 0);
const inset = computed(() => Math.max(10, radius.value - 6) + "px");
function start(e) {
	active.value = true;
	const zoom = canvas_zoom(e.currentTarget);
	const ox = e.clientX;
	const oy = e.clientY;
	const start_val = radius.value;

	function move(ev) {
		// dragging toward the section centre (down-right) grows the radius
		const delta = (ev.clientX - ox + (ev.clientY - oy)) / 2 / zoom;
		props.target[props.prop] = Math.max(0, Math.round(start_val + delta));
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
	top: calc(var(--pfb-radius-top, 0px) + min(var(--pfb-radius-inset), calc(50% - 6px)));
	left: min(var(--pfb-radius-inset), calc(50% - 6px));
	width: 12px;
	height: 12px;
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
