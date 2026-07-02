<template>
	<!-- Window chrome shared by EmailComposer/CommentComposer/MultiComposer: trigger
		 bar, FloatingWindow, docked-resize grip, header (title arrives via slot). -->
	<!-- Trigger and window are fragment siblings under one persistent wrapper (not
		 nested directly — FloatingWindow's root is a <Teleport>, so wrapping them in a
		 <Transition> would break Vue's leave hook). The wrapper itself never unmounts
		 as isCollapsed flips, so pointer capture set on it during a docked-resize drag
		 survives the trigger/window swap — see startDockedResize. -->
	<div ref="rootEl">
		<button
			v-if="isCollapsed"
			type="button"
			class="ec-trigger flex w-full cursor-pointer items-center gap-3 rounded-lg border border-outline-gray-2 bg-surface-white px-4 py-2.5 text-left shadow-sm hover:border-outline-gray-3 hover:bg-surface-gray-1"
			@click="onTriggerClick"
		>
			<Avatar
				:image="avatar || currentUser.image || ''"
				:label="avatarLabel || currentUser.fullname || ''"
				size="sm"
				class="shrink-0"
			/>
			<span class="text-base text-ink-gray-5">{{ placeholder || "Type a message…" }}</span>
		</button>

		<!-- `:style` falls through onto FloatingWindow's panel; docked uses it to pin a
			 draggable height (undefined while floating/minimized). -->
		<FloatingWindow
			v-if="!isCollapsed"
			key="expanded"
			v-model:mode="windowMode"
			:minimizable="minimizable"
			:style="dockedStyle"
		>
			<template #header="{ mode, float, dock, expandFromTray }">
				<!-- Docked-only grip: drag down to collapse, up to grow the compose area. -->
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
					:minimizable="minimizable"
					:minimized="mode === 'minimized'"
					@expand="
						mode === 'docked'
							? float()
							: mode === 'floating'
							? dock()
							: expandFromTray()
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
	</div>
</template>

<script setup lang="ts">
import { computed, ref, useTemplateRef } from "vue";
import { Avatar } from "frappe-ui";
import { FloatingWindow, type WindowMode } from "frappe-ui/experimental";
import ComposerHeader from "./ComposerHeader.vue";
import { currentUserInfo } from "./currentUser";

const props = withDefaults(
	defineProps<{
		/** Plain title; also the label shown on the minimized tray strip. */
		title?: string;
		/** Show the pop-out/dock control. */
		expandable?: boolean;
		/** Show the minimize-to-tray ("save and close") control. */
		minimizable?: boolean;
		/** Mount already expanded instead of behind the collapsed trigger bar. */
		startExpanded?: boolean;
		/** Avatar + placeholder for the collapsed trigger bar. Defaults to the signed-in
		 *  user (from `frappe.boot`) — pass these to override. */
		avatar?: string;
		avatarLabel?: string;
		placeholder?: string;
	}>(),
	{ title: "", expandable: true, minimizable: true, startExpanded: false }
);

const rootEl = useTemplateRef<HTMLElement>("rootEl");
const windowMode = defineModel<WindowMode>("mode", { default: "docked" });
const currentUser = computed(() => currentUserInfo());

// --- Collapsed / expanded ----------------------------------------------------

const isCollapsed = ref(!props.startExpanded);

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

// A drag that ends collapsed leaves the trigger bar under the pointer, and the
// browser synthesizes a click on release — swallow it for a moment so that
// same gesture doesn't instantly reopen what it just collapsed.
let dragCollapsedAt = 0;
function onTriggerClick() {
	if (Date.now() - dragCollapsedAt < 300) return;
	expand();
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

// Drag up to grow the window, down to collapse it — never releases the drag on
// its own. Pointer capture goes on the wrapper (not the grip, which unmounts
// the moment the drag collapses the panel) so it survives that swap and an
// upward pull can reopen and keep resizing without the user re-gripping.
function startDockedResize(event: PointerEvent) {
	const grip = event.currentTarget as HTMLElement;
	const captureTarget = rootEl.value ?? grip;
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
			if (!isCollapsed.value) collapse();
			return;
		}
		if (isCollapsed.value) {
			isCollapsed.value = false;
			windowMode.value = "docked";
		}
		let clamped = Math.min(Math.max(next, 0), window.innerHeight);
		// Growing docked height shrinks sibling content above it (a flex-1 scroll
		// area), which pushes the panel's top edge up. Once that sibling has no more
		// room to give, forcing more height on the panel no longer moves its top — it
		// just pushes the bottom off-screen. Re-query the panel (the drag may have
		// collapsed and reopened it, replacing the element) and refuse to grow past
		// the point where its rendered top stops moving.
		const panel = rootEl.value?.querySelector(".floating-window") as HTMLElement | null;
		if (panel && clamped > (dockedHeight.value ?? 0)) {
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
		if (isCollapsed.value) dragCollapsedAt = Date.now();
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

defineExpose({ expand, collapse, isCollapsed: computed(() => isCollapsed.value) });
</script>
