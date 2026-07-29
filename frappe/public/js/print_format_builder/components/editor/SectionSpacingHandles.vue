<template>
	<div class="pfb-spacing-handles">
		<template v-for="side in sides" :key="side">
			<!-- translucent band showing the current padding on this side -->
			<div class="pfb-pad-band" :style="band_style[side]"></div>
			<!-- small grab handle centered on the padding/content boundary -->
			<div
				class="pfb-pad-grip"
				:class="['pfb-pad-grip-' + side, { active: active === side }]"
				:style="grip_style[side]"
				:title="__('Drag to change {0} padding', [side])"
				@pointerdown.stop.prevent="start(side, $event)"
			>
				<span v-if="active === side" class="pfb-pad-tip">{{ pad[side] || 0 }}</span>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps(["section"]);
const sides = ["top", "right", "bottom", "left"];
const active = ref(null);

const pad = computed(() => props.section.padding || { top: 0, right: 0, bottom: 0, left: 0 });

const band_style = computed(() => ({
	top: { top: 0, left: 0, right: 0, height: (pad.value.top || 0) + "px" },
	bottom: { bottom: 0, left: 0, right: 0, height: (pad.value.bottom || 0) + "px" },
	left: { left: 0, top: 0, bottom: 0, width: (pad.value.left || 0) + "px" },
	right: { right: 0, top: 0, bottom: 0, width: (pad.value.right || 0) + "px" },
}));

const grip_style = computed(() => ({
	top: { top: (pad.value.top || 0) + "px", left: "50%" },
	bottom: { bottom: (pad.value.bottom || 0) + "px", left: "50%" },
	left: { left: (pad.value.left || 0) + "px", top: "50%" },
	right: { right: (pad.value.right || 0) + "px", top: "50%" },
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

/* padding region — like the builder's shaded spacing band */
.pfb-pad-band {
	position: absolute;
	background: var(--pfb-accent);
	opacity: 0.14;
}

/* small draggable handle sitting on the padding boundary */
.pfb-pad-grip {
	position: absolute;
	pointer-events: auto;
	background: var(--pfb-accent);
	border: 1.5px solid var(--fg-color);
	border-radius: 6px;
	box-shadow: var(--shadow-sm);
}

.pfb-pad-grip-top,
.pfb-pad-grip-bottom {
	width: 26px;
	height: 6px;
	cursor: ns-resize;
}
.pfb-pad-grip-left,
.pfb-pad-grip-right {
	width: 6px;
	height: 26px;
	cursor: ew-resize;
}

.pfb-pad-grip-top {
	transform: translate(-50%, -50%);
}
.pfb-pad-grip-bottom {
	transform: translate(-50%, 50%);
}
.pfb-pad-grip-left {
	transform: translate(-50%, -50%);
}
.pfb-pad-grip-right {
	transform: translate(50%, -50%);
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
