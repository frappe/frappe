<template>
	<div class="pfb-spacing-handles">
		<div
			v-for="side in sides"
			:key="side"
			class="pfb-pad-handle"
			:class="['pfb-pad-' + side, { active: active === side }]"
			:style="handle_pos[side]"
			:title="__('Drag to change {0} padding', [side])"
			@pointerdown.stop.prevent="start(side, $event)"
		>
			<span v-if="active === side" class="pfb-pad-tip">{{ pad[side] || 0 }}</span>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps(["section"]);
const sides = ["top", "right", "bottom", "left"];
const active = ref(null);

const pad = computed(() => props.section.padding || { top: 0, right: 0, bottom: 0, left: 0 });

// handles sit on the padding/content boundary of each side
const handle_pos = computed(() => ({
	top: { top: (pad.value.top || 0) + "px", left: 0, right: 0 },
	bottom: { bottom: (pad.value.bottom || 0) + "px", left: 0, right: 0 },
	left: { left: (pad.value.left || 0) + "px", top: 0, bottom: 0 },
	right: { right: (pad.value.right || 0) + "px", top: 0, bottom: 0 },
}));

function canvas_zoom(el) {
	const c = el.closest(".print-format-container");
	return parseFloat(c && getComputedStyle(c).getPropertyValue("--pfb-zoom")) || 1;
}

function start(side, e) {
	active.value = side;
	const zoom = canvas_zoom(e.currentTarget);
	const vertical = side === "top" || side === "bottom";
	const axis = vertical ? "clientY" : "clientX";
	// dragging inward (down/right for top/left, up/left for bottom/right) grows padding
	const sign = side === "top" || side === "left" ? 1 : -1;
	const origin = e[axis];
	const box = { top: 0, right: 0, bottom: 0, left: 0, ...props.section.padding };
	const start_val = box[side];

	function move(ev) {
		const delta = ((ev[axis] - origin) / zoom) * sign;
		props.section.padding = { ...box, [side]: Math.max(0, Math.round(start_val + delta)) };
	}
	function up() {
		active.value = null;
		window.removeEventListener("pointermove", move);
		window.removeEventListener("pointerup", up);
	}
	window.addEventListener("pointermove", move);
	window.addEventListener("pointerup", up);
}
</script>

<style scoped>
.pfb-spacing-handles {
	position: absolute;
	inset: 0;
	pointer-events: none;
	z-index: 3;
}

.pfb-pad-handle {
	position: absolute;
	pointer-events: auto;
	background: transparent;
}

/* thin accent line on the padding boundary, shown on hover/drag */
.pfb-pad-handle::before {
	content: "";
	position: absolute;
	background: var(--pfb-accent);
	opacity: 0;
	transition: opacity 0.1s;
}

.pfb-pad-handle:hover::before,
.pfb-pad-handle.active::before {
	opacity: 1;
}

.pfb-pad-top,
.pfb-pad-bottom {
	height: 9px;
	margin-top: -4px;
	cursor: ns-resize;
}
.pfb-pad-left,
.pfb-pad-right {
	width: 9px;
	margin-left: -4px;
	cursor: ew-resize;
}

.pfb-pad-top::before,
.pfb-pad-bottom::before {
	left: 0;
	right: 0;
	top: 50%;
	height: 2px;
	transform: translateY(-50%);
}
.pfb-pad-left::before,
.pfb-pad-right::before {
	top: 0;
	bottom: 0;
	left: 50%;
	width: 2px;
	transform: translateX(-50%);
}

.pfb-pad-tip {
	position: absolute;
	top: 50%;
	left: 50%;
	transform: translate(-50%, -50%);
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
