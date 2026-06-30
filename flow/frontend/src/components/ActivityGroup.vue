<script setup>
import { computed, ref } from "vue";
import { FeatherIcon } from "@/lib/ui";
import ActivityLabel from "./ActivityLabel.vue";
import ActivityStep from "./ActivityStep.vue";
import ArgsView from "./ArgsView.vue";
import { toolLabel, argEntries } from "@/lib/toolMeta";
import { __ } from "@/lib/translate";

// Tool calls as one collapsible line: running → active step's label; done → latest
// label, or "Ran N steps" once `sealed` (text/approval follows). From frappe/flow#9.
const props = defineProps({
	parts: { type: Array, required: true },
	sealed: { type: Boolean, default: false },
	live: { type: Boolean, default: false },
});

const isRunning = (p) => p.result === null && p.approval === null;
const running = computed(() => props.parts.some(isRunning));
const single = computed(() => props.parts.length === 1);
// Live + unsealed = still working (a tool running, or thinking between steps).
const shimmer = computed(() => props.live && !props.sealed);

const summary = computed(() => {
	if (running.value) return toolLabel(props.parts.find(isRunning).name);
	if (props.sealed && !single.value) return __("Ran {0} steps", [props.parts.length]);
	return toolLabel(props.parts[props.parts.length - 1].name);
});

// Only set on a resolved approval line.
const status = computed(() => {
	const a = single.value ? props.parts[0].approval : null;
	if (a === "denied") return __("Denied");
	if (a === "redirected") return __("Changes requested");
	return "";
});

// A lone step with no inputs has nothing to reveal.
const expandable = computed(
	() => !single.value || argEntries(props.parts[0].arguments).length > 0
);
const open = ref(false);
function toggle() {
	if (expandable.value) open.value = !open.value;
}
</script>

<template>
	<div class="my-0.5">
		<button
			class="flex items-center gap-1.5 text-sm text-ink-gray-5 transition-colors"
			:class="[
				expandable && !running ? 'hover:text-ink-gray-7' : '',
				expandable ? '' : 'cursor-default',
			]"
			@click="toggle"
		>
			<ActivityLabel :text="summary" :active="shimmer" />
			<span v-if="status" class="text-xs text-ink-gray-5">· {{ status }}</span>
			<FeatherIcon
				v-if="expandable"
				name="chevron-right"
				class="mt-0.5 h-3.5 w-3.5 shrink-0 transition-transform"
				:class="{ 'rotate-90': open }"
			/>
		</button>

		<Transition name="flow-reveal">
			<div v-if="open">
				<!-- Single step: its inputs directly. Multiple: a connected timeline. -->
				<ArgsView v-if="single" :arguments="parts[0].arguments" class="mt-2" />
				<div v-else class="relative mt-1.5">
					<span
						class="absolute bottom-2.5 left-[7px] top-2.5 w-px bg-surface-gray-3"
						aria-hidden="true"
					></span>
					<ActivityStep
						v-for="(part, i) in parts"
						:key="part.id ?? i"
						:part="part"
						:live="live"
					/>
				</div>
			</div>
		</Transition>
	</div>
</template>

<style scoped>
.flow-reveal-enter-active,
.flow-reveal-leave-active {
	transition: opacity 0.15s ease;
}
.flow-reveal-enter-from,
.flow-reveal-leave-to {
	opacity: 0;
}
</style>
