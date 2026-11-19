<template>
	<div class="flex h-full py-10" :class="side === 'start' ? 'pe-10' : 'ps-10'">
		<div
			ref="windowEl"
			inert
			aria-hidden="true"
			data-slot="setup-preview-window"
			class="setup-preview-open flex min-h-0 flex-1 overflow-hidden border border-outline-gray-2 bg-surface-base shadow-2xl"
			:class="side === 'start' ? 'rounded-e-8 border-s-0' : 'rounded-s-8 border-e-0'"
			:style="expandStyle"
			@transitionend.self="settle"
		>
			<div v-if="appWidth" class="relative min-w-0 flex-1 overflow-hidden">
				<div class="absolute start-0 top-0 flex" :style="scaledStyle">
					<slot />
				</div>
			</div>
			<slot v-else />
		</div>
	</div>
</template>

<script setup lang="ts">
import { useElementSize } from "@vueuse/core";
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import type { CSSProperties } from "vue";

const props = withDefaults(
	defineProps<{
		/** The screen edge the window sits flush against; the same side as SetupFlow's `previewSide`. */
		side?: "start" | "end";
		/** True grows the window over the whole screen, so the setup hands over to the app it previews. */
		expanded?: boolean;
		/**
		 * Lays the app out at this width in pixels and scales it to fit, so its own breakpoints
		 * pick the desktop layout. Unset, the app gets the window's real width.
		 */
		appWidth?: number;
	}>(),
	{ side: "end", expanded: false, appWidth: undefined }
);

const emit = defineEmits<{
	/** The window covers the screen: the host can navigate to the app now. */
	expanded: [];
}>();

defineSlots<{
	/** The app as it is being set up, built from the app's own components. */
	default?: () => unknown;
}>();

const EXPAND = "600ms cubic-bezier(0.33, 1, 0.68, 1)";
const windowEl = ref<HTMLElement | null>(null);
const expandStyle = ref<CSSProperties>({});

const { width: windowWidth, height: windowHeight } = useElementSize(windowEl);
const scaledStyle = computed<CSSProperties>(() => {
	if (!props.appWidth || !windowWidth.value) return {};
	const scale = Math.min(1, windowWidth.value / props.appWidth);
	const rtl = document.documentElement.dir === "rtl";
	return {
		width: `${windowWidth.value / scale}px`,
		height: `${windowHeight.value / scale}px`,
		transform: `scale(${scale})`,
		transformOrigin: rtl ? "top right" : "top left",
	};
});
let settled = false;
let fallback: ReturnType<typeof setTimeout> | undefined;

function settle() {
	if (settled || !props.expanded) return;
	settled = true;
	clearTimeout(fallback);
	emit("expanded");
}

watch(
	() => props.expanded,
	async (expanded) => {
		if (!expanded || !windowEl.value) return;
		const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
		const { top, left, width, height } = windowEl.value.getBoundingClientRect();
		// Fixed at its current place first, then grown to the screen, so the move animates.
		expandStyle.value = {
			position: "fixed",
			zIndex: 50,
			top: `${top}px`,
			left: `${left}px`,
			width: `${width}px`,
			height: `${height}px`,
		};
		if (reduced) return settle();
		await nextTick();
		// Lay out the starting place before the end one is set, or the browser skips the move.
		windowEl.value?.getBoundingClientRect();
		requestAnimationFrame(() => {
			expandStyle.value = {
				...expandStyle.value,
				top: "0px",
				left: "0px",
				width: "100vw",
				height: "100vh",
				borderRadius: "0px",
				transition: ["top", "left", "width", "height", "border-radius"]
					.map((property) => `${property} ${EXPAND}`)
					.join(", "),
			};
		});
		// A background tab can skip transitionend; the hand-over must still happen.
		fallback = setTimeout(settle, 800);
	}
);

onBeforeUnmount(() => clearTimeout(fallback));
</script>

<style scoped>
@media (prefers-reduced-motion: no-preference) {
	.setup-preview-open {
		animation: setup-preview-open 400ms cubic-bezier(0.16, 1, 0.3, 1) backwards;
	}
}

@keyframes setup-preview-open {
	from {
		opacity: 0;
		transform: scale(0.98);
	}
}
</style>
