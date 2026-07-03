<template>
	<!-- Root of the compound composer: owns the state and
		 provides it to ComposerTrigger / ComposerContent / ComposerChannel; renders
		 nothing but a persistent wrapper. The wrapper never unmounts, so pointer
		 capture set on it during ComposerContent's docked-resize drag survives the
		 trigger/window swap. -->
	<div ref="rootElement">
		<slot />
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, shallowRef, toRef, useTemplateRef, watch } from "vue";
import { type WindowMode } from "frappe-ui/experimental";
import { provideComposer, type ChannelEntry } from "./composerContext";

const props = withDefaults(
	defineProps<{
		/**
		 * Whether the composer can collapse (minimize) to its trigger bar.
		 *
		 * When true (default) the composer toggles between the collapsed
		 * ComposerTrigger and the open window. When false it is pinned open:
		 * there is nothing to collapse to, so any ComposerTrigger stays hidden
		 * and the minimize control is dropped rather than left inert.
		 */
		minimizable?: boolean;
	}>(),
	{ minimizable: true }
);

// The primary two-way axis: is the window open, or collapsed to the trigger bar?
const open = defineModel<boolean>("open", { default: false });
// A non-minimizable composer has no trigger to reveal it, so it must start
// (and stay) open — otherwise it would render nothing the user could act on.
if (!props.minimizable) open.value = true;
// Active channel, by <ComposerChannel value>; defaults to the first one.
const channel = defineModel<string>("channel", { default: "" });
// Kept as `mode` for consistency with FloatingWindow's own v-model.
const mode = defineModel<WindowMode>("mode", { default: "docked" });

const rootElement = useTemplateRef<HTMLElement>("rootElement");
const channels = shallowRef<ChannelEntry[]>([]);
const dragCollapsedAt = ref(0);

provideComposer({
	open,
	channel,
	mode,
	channels,
	register: (entry) => (channels.value = [...channels.value, entry]),
	unregister: (value) => (channels.value = channels.value.filter((c) => c.value !== value)),
	minimizable: toRef(props, "minimizable"),
	// Collapse the window back to its trigger. A no-op when the composer is
	// pinned open (not minimizable), so callers — the minimize control, the
	// drag-to-collapse gesture, the editor's discard — need no special-casing.
	close: () => {
		if (props.minimizable) open.value = false;
	},
	rootElement,
	dragCollapsedAt,
});

// Keep `channel` valid: default to the first registered channel, move off one
// that unregisters.
watch(channels, (list) => {
	if (!list.find((c) => c.value === channel.value)) channel.value = list[0]?.value ?? "";
});

const activeChannel = computed(() => channels.value.find((c) => c.value === channel.value));

watch(open, (isOpen) => {
	if (isOpen) {
		nextTick(() => activeChannel.value?.surface?.focus());
	} else {
		// Reopen docked, however the window was left.
		mode.value = "docked";
	}
});
</script>
