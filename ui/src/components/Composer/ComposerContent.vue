<template>
	<!-- The window: FloatingWindow + header, with a channel switcher when several
		 <ComposerChannel>s are slotted in, and a docked-resize grip. Stays mounted
		 while the composer is closed — `display: none` falls through onto the panel
		 via `:style` — so channel drafts survive close/reopen without any state
		 hoisting. -->
	<!-- We always supply our own `#header` (below), which FloatingWindow renders
		 in place of its built-in title bar — so FloatingWindow's own `minimizable`
		 prop (gating a button in that built-in bar) never applies here and is
		 intentionally left at its default. -->
	<FloatingWindow v-model:mode="mode" :style="panelStyle">
		<template #header="{ mode: windowMode, float, dock, expandFromTray }">
			<!-- Docked-only grip: drag down to collapse (minimize), up to grow the
				 compose area. It's a minimize affordance first, so it's shown only
				 when the window is actually minimizable — a pinned-open window has
				 nothing to collapse to. -->
			<button
				v-if="windowMode === 'docked' && minimizable"
				type="button"
				aria-label="Resize composer"
				class="absolute left-1/2 top-0 z-10 flex h-6 w-24 -translate-x-1/2 cursor-ns-resize touch-none items-center justify-center rounded-full opacity-60 transition-opacity hover:opacity-100 focus:opacity-100"
				@pointerdown.prevent="startDockedResize"
			>
				<span class="h-1 w-10 rounded-full bg-surface-gray-4" />
			</button>
			<ComposerHeader
				class="px-2.5"
				:title="headerTitle"
				:floatable="floatable"
				:floating="windowMode === 'floating'"
				:minimizable="minimizable"
				:minimized="windowMode === 'minimized'"
				@expand="
					windowMode === 'docked'
						? float()
						: windowMode === 'floating'
						? dock()
						: expandFromTray()
				"
				@minimize="close()"
			>
				<!-- Channel switcher, only when there is something to switch between;
					 minimized falls back to the plain title inside ComposerHeader. -->
				<template v-if="channels.length > 1 && windowMode !== 'minimized'" #title>
					<TabButtons v-model="channel" :options="channelOptions" />
				</template>

				<!-- Optional override for the window controls. Forwarded down to
					 ComposerHeader's `actions` slot, which otherwise renders the
					 default expand/minimize buttons. The forwarded slot props carry
					 the `expand` / `minimize` actions (and `floating` state) so a
					 consumer's own controls can still drive real window behavior.
					 Exposed under a distinct name so it is not confused with the
					 editor's own `actions` slot (the footer button row). -->
				<template v-if="$slots['header-actions']" #actions="actionProps">
					<slot name="header-actions" v-bind="actionProps" />
				</template>
			</ComposerHeader>
		</template>

		<slot />
	</FloatingWindow>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { TabButtons } from "frappe-ui";
import { FloatingWindow } from "frappe-ui/experimental";
import ComposerHeader from "./ComposerHeader.vue";
import { requireComposer } from "./composerContext";

const props = withDefaults(
	defineProps<{
		/** Header/tray text; defaults to the active channel's label. */
		title?: string;
		/** Show the pop-out/dock control. */
		floatable?: boolean;
	}>(),
	{ title: "", floatable: true }
);

const composer = requireComposer("ComposerContent");
const { open, channel, mode, channels, minimizable, close, rootElement, dragCollapsedAt } =
	composer;

const channelOptions = computed(() =>
	channels.value.map((c) => ({ label: c.label, value: c.value }))
);
const activeChannel = computed(() => channels.value.find((c) => c.value === channel.value));
const headerTitle = computed(() => props.title || activeChannel.value?.label || "");

// --- Docked resize -----------------------------------------------------------

// Dragging below this height collapses back to the trigger bar.
const COLLAPSE_THRESHOLD = 230;

const dockedHeight = ref<number | null>(null);

// Reopen with auto height, however the resize drag left the window.
watch(open, (isOpen) => {
	if (!isOpen) dockedHeight.value = null;
});

// `:style` falls through onto FloatingWindow's panel: hides it while closed,
// pins a draggable height while docked.
const panelStyle = computed(() => {
	if (!open.value) return { display: "none" };
	return mode.value === "docked" && dockedHeight.value
		? { height: `${dockedHeight.value}px` }
		: undefined;
});

// Drag up to grow the window, down to collapse it — never releases the drag on
// its own. Pointer capture goes on the root wrapper (not the grip, which is
// hidden the moment the drag collapses the panel) so it survives that swap and
// an upward pull can reopen and keep resizing without the user re-gripping.
function startDockedResize(event: PointerEvent) {
	const grip = event.currentTarget as HTMLElement;
	const captureTarget = rootElement.value ?? grip;
	captureTarget.setPointerCapture?.(event.pointerId);
	let startY = event.clientY;
	let startHeight =
		dockedHeight.value ??
		grip.closest(".floating-window")?.getBoundingClientRect().height ??
		0;
	document.body.style.cursor = "ns-resize";
	document.body.style.userSelect = "none";

	function onMove(e: PointerEvent) {
		const next = startHeight - (e.clientY - startY);
		// Collapse only on a net-downward drag past the threshold — an upward drag on
		// a short window (e.g. comment) must grow it, not snap it shut. Either way the
		// drag stays live: pulling back up past the threshold reopens and keeps resizing.
		if (e.clientY > startY && next < COLLAPSE_THRESHOLD) {
			if (open.value) close();
			return;
		}
		if (!open.value) open.value = true;
		let clamped = Math.min(Math.max(next, 0), window.innerHeight);
		// Growing docked height shrinks sibling content above it (a flex-1 scroll
		// area), which pushes the panel's top edge up. Once that sibling has no more
		// room to give, forcing more height on the panel no longer moves its top — it
		// just pushes the bottom off-screen. Refuse to grow past the point where the
		// rendered top stops moving. `offsetWidth` skips the check while the panel is
		// still display:none right after a mid-drag reopen (styles flush async).
		const panel = rootElement.value?.querySelector(".floating-window") as HTMLElement | null;
		if (panel && panel.offsetWidth && clamped > (dockedHeight.value ?? 0)) {
			const topBefore = panel.getBoundingClientRect().top;
			panel.style.height = `${clamped}px`;
			const topAfter = panel.getBoundingClientRect().top;
			if (topAfter >= topBefore) {
				clamped = dockedHeight.value ?? 0;
				panel.style.height = clamped ? `${clamped}px` : "";
			}
		}
		dockedHeight.value = clamped;
		// Rebase whenever a bound clips the value, so the pointer can't drift past the
		// edge and build up a dead zone before reversal takes effect.
		if (clamped !== next) {
			startY = e.clientY;
			startHeight = clamped;
		}
	}
	function onUp() {
		if (!open.value) dragCollapsedAt.value = Date.now();
		captureTarget.releasePointerCapture?.(event.pointerId);
		document.body.style.cursor = "";
		document.body.style.userSelect = "";
		window.removeEventListener("pointermove", onMove);
		window.removeEventListener("pointerup", onUp);
		window.removeEventListener("pointercancel", onUp);
	}
	window.addEventListener("pointermove", onMove);
	window.addEventListener("pointerup", onUp);
	window.addEventListener("pointercancel", onUp);
}
</script>
