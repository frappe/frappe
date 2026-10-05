<template>
	<div class="pfb-spacing-handles" :class="'pfb-spacing-' + type">
		<template v-for="side in sides" :key="side">
			<!-- translucent band showing the current spacing on this side -->
			<div class="pfb-space-band" :style="band_style[side]"></div>
			<!-- small grab handle sitting on the spacing boundary -->
			<div
				class="pfb-space-grip"
				:class="['pfb-space-grip-' + side, { active: active === side }]"
				:style="grip_style[side]"
				:title="__('Drag to change {0} {1}', [side, type])"
				@pointerdown.stop.prevent="start(side, $event)"
			>
				<span v-if="active === side" class="pfb-space-tip">{{ box[side] || 0 }}</span>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { canvas_zoom } from "../../utils";

const props = defineProps({
	section: { type: Object, required: true },
	type: { type: String, default: "padding" }, // "padding" (inside) | "margin" (outside)
});
const sides = ["top", "right", "bottom", "left"];
const active = ref(null);

// margin sits outside the border, so its bands/handles are offset the other way
const outward = computed(() => (props.type === "margin" ? -1 : 1));
const box = computed(() => props.section[props.type] || { top: 0, right: 0, bottom: 0, left: 0 });
const edge = (side) => (outward.value < 0 ? -(box.value[side] || 0) : 0);

// grips never sit closer than this to the border, so the inside (padding) and
// outside (margin) handles stay visibly separated even at zero — matching the
// website builder, where both affordances are always on screen
const GRIP_GAP = 5;
const grip_off = (side) => {
	const off = Math.max(box.value[side] || 0, GRIP_GAP);
	return outward.value < 0 ? -off : off;
};

const band_style = computed(() => ({
	top: { top: edge("top") + "px", left: 0, right: 0, height: (box.value.top || 0) + "px" },
	bottom: {
		bottom: edge("bottom") + "px",
		left: 0,
		right: 0,
		height: (box.value.bottom || 0) + "px",
	},
	left: { left: edge("left") + "px", top: 0, bottom: 0, width: (box.value.left || 0) + "px" },
	right: {
		right: edge("right") + "px",
		top: 0,
		bottom: 0,
		width: (box.value.right || 0) + "px",
	},
}));

const grip_style = computed(() => ({
	top: { top: grip_off("top") + "px", left: "50%" },
	bottom: { bottom: grip_off("bottom") + "px", left: "50%" },
	left: { left: grip_off("left") + "px", top: "50%" },
	right: { right: grip_off("right") + "px", top: "50%" },
}));

function start(side, e) {
	active.value = side;
	const zoom = canvas_zoom(e.currentTarget);
	const axis = side === "top" || side === "bottom" ? "clientY" : "clientX";
	// dragging away from the content grows the spacing; margin is the mirror of padding
	const base = side === "top" || side === "left" ? 1 : -1;
	const sign = base * outward.value;
	const origin = e[axis];
	const start_box = { top: 0, right: 0, bottom: 0, left: 0, ...props.section[props.type] };
	const start_val = start_box[side];

	function move(ev) {
		const delta = ((ev[axis] - origin) / zoom) * sign;
		props.section[props.type] = {
			...start_box,
			[side]: Math.max(0, Math.round(start_val + delta)),
		};
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
.pfb-spacing-padding {
	--spacing-color: var(--pfb-accent);
}
.pfb-spacing-margin {
	--spacing-color: var(--orange-400, #f5a623);
}

.pfb-space-band {
	position: absolute;
	background: var(--spacing-color);
	opacity: 0.14;
}

/* small tick marks, not chunky pills — the hit area is widened separately so
   they stay easy to grab (see ::before) */
.pfb-space-grip {
	position: absolute;
	pointer-events: auto;
	background: var(--spacing-color);
	border-radius: 2px;
}

.pfb-space-grip::before {
	content: "";
	position: absolute;
	inset: -6px;
}

.pfb-space-grip-top,
.pfb-space-grip-bottom {
	width: 14px;
	height: 3px;
	cursor: ns-resize;
}
.pfb-space-grip-left,
.pfb-space-grip-right {
	width: 3px;
	height: 14px;
	cursor: ew-resize;
}

.pfb-space-grip-top {
	transform: translate(-50%, -50%);
}
.pfb-space-grip-bottom {
	transform: translate(-50%, 50%);
}
.pfb-space-grip-left {
	transform: translate(-50%, -50%);
}
.pfb-space-grip-right {
	transform: translate(50%, -50%);
}

.pfb-space-tip {
	position: absolute;
	top: 50%;
	left: 50%;
	transform: translate(-50%, -50%);
	background: var(--spacing-color);
	color: #fff;
	font-size: var(--text-tiny);
	line-height: 1;
	padding: 2px 5px;
	border-radius: var(--radius-sm);
	white-space: nowrap;
	pointer-events: none;
}
</style>
