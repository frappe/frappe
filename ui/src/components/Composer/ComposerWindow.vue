<template>
	<!-- Window chrome shared by EmailComposer/CommentComposer/MultiComposer: trigger
		 bar, FloatingWindow, docked-resize grip, header (title arrives via slot). -->
	<!-- Trigger and window are fragment siblings, not nested — FloatingWindow's root
		 is a <Teleport>, so wrapping them in a <Transition> would break Vue's leave hook. -->
	<button
		v-if="isCollapsed"
		type="button"
		class="ec-trigger flex w-full cursor-pointer items-center gap-3 rounded-lg border border-outline-gray-2 bg-surface-white px-4 py-2.5 text-left shadow-sm transition-shadow hover:shadow"
		@click="expand"
	>
		<Avatar :image="avatar || ''" :label="avatarLabel || ''" size="sm" class="shrink-0" />
		<span class="text-base text-ink-gray-7">{{ placeholder || "Type a message…" }}</span>
	</button>

	<!-- `:style` falls through onto FloatingWindow's panel; docked uses it to pin a
		 draggable height (undefined while floating/minimized). -->
	<FloatingWindow
		v-if="!isCollapsed"
		key="expanded"
		v-model:mode="windowMode"
		:minimizable="true"
		:style="dockedStyle"
	>
		<template #header="{ mode, float, dock, expandFromTray }">
			<!-- Docked-only grip: drag up to grow the compose area. -->
			<button
				v-if="mode === 'docked'"
				type="button"
				aria-label="Resize composer"
				class="absolute left-1/2 top-0 z-10 flex h-6 w-24 -translate-x-1/2 cursor-ns-resize touch-none items-center justify-center rounded-full opacity-60 transition-opacity hover:opacity-100 focus:opacity-100"
				@pointerdown.prevent="startDockedResize"
			>
				<span class="h-1 w-10 rounded-full bg-surface-gray-4" />
			</button>
			<ComposerHeader
				class="px-2.5"
				:title="title"
				:expandable="expandable"
				:floating="mode === 'floating'"
				:minimizable="true"
				:minimized="mode === 'minimized'"
				@expand="
					mode === 'docked' ? float() : mode === 'floating' ? dock() : expandFromTray()
				"
				@minimize="collapse()"
			>
				<!-- Host title (e.g. MultiComposer's channel switcher); minimized falls
					 back to the plain `title` text inside ComposerHeader. -->
				<template v-if="$slots.title && mode !== 'minimized'" #title>
					<slot name="title" />
				</template>
			</ComposerHeader>
		</template>

		<slot />
	</FloatingWindow>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Avatar } from "frappe-ui";
import { FloatingWindow, type WindowMode } from "frappe-ui/experimental";
import ComposerHeader from "./ComposerHeader.vue";

withDefaults(
	defineProps<{
		/** Plain title; also the label shown on the minimized tray strip. */
		title?: string;
		/** Show the pop-out/dock control. */
		expandable?: boolean;
		/** Avatar + placeholder for the collapsed trigger bar. */
		avatar?: string;
		avatarLabel?: string;
		placeholder?: string;
	}>(),
	{ title: "", expandable: true }
);

const windowMode = defineModel<WindowMode>("mode", { default: "docked" });

// --- Collapsed / expanded ----------------------------------------------------

const isCollapsed = ref(true);

/** Open the window; resolves once the panel has mounted (after the transition),
 *  so callers can focus or seed the freshly-rendered body. */
function expand(): Promise<void> {
	if (!isCollapsed.value) return Promise.resolve();
	isCollapsed.value = false;
	windowMode.value = "docked";
	return new Promise((resolve) => setTimeout(resolve, 180));
}

function collapse() {
	isCollapsed.value = true;
	dockedHeight.value = null;
}

// --- Docked resize -----------------------------------------------------------

// Dragging below this height collapses back to the trigger bar.
const COLLAPSE_THRESHOLD = 230;

const dockedHeight = ref<number | null>(null);

const dockedStyle = computed(() =>
	windowMode.value === "docked" && dockedHeight.value
		? { height: `${dockedHeight.value}px` }
		: undefined
);

// Drag up to grow the window; seed from the rendered height so there's no jump.
// setPointerCapture pins pointer events to the grip so editor content (images,
// links) can't steal them mid-drag.
function startDockedResize(event: PointerEvent) {
	const grip = event.currentTarget as HTMLElement;
	const panel = grip.closest(".floating-window") as HTMLElement | null;
	grip.setPointerCapture(event.pointerId);
	const startY = event.clientY;
	const startHeight = dockedHeight.value ?? panel?.offsetHeight ?? 0;

	function onMove(e: PointerEvent) {
		const next = startHeight - (e.clientY - startY);
		// Collapse only on a downward drag past the threshold — an upward drag on
		// a short window (e.g. comment) must grow it, not snap it shut.
		if (e.clientY > startY && next < COLLAPSE_THRESHOLD) {
			collapse();
			cleanup();
		} else {
			dockedHeight.value = Math.min(Math.max(next, 0), window.innerHeight);
		}
	}
	function cleanup() {
		window.removeEventListener("pointermove", onMove);
		window.removeEventListener("pointerup", cleanup);
	}
	window.addEventListener("pointermove", onMove);
	window.addEventListener("pointerup", cleanup);
}

defineExpose({ expand, collapse, isCollapsed: computed(() => isCollapsed.value) });
</script>
