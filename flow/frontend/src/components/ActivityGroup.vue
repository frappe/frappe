<script setup>
import { computed, ref } from "vue";
import { FeatherIcon } from "@/lib/ui";
import ActivityLabel from "./ActivityLabel.vue";
import ActivityStep from "./ActivityStep.vue";
import ArgsView from "./ArgsView.vue";
import ToolError from "./ToolError.vue";
import { toolLabel, hasArgs, toolError } from "@/lib/toolMeta";
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

// A single tool call whose result is an error payload.
const error = computed(() => (single.value ? toolError(props.parts[0].result) : null));

// Only set on a resolved approval or failed line.
const status = computed(() => {
	if (error.value) return __("Failed");
	const a = single.value ? props.parts[0].approval : null;
	if (a === "denied") return __("Denied");
	if (a === "redirected") return __("Changes requested");
	return "";
});

// A lone step reveals its inputs, or its error when it failed with none.
const expandable = computed(
	() => !single.value || hasArgs(props.parts[0].arguments) || Boolean(error.value)
);
const open = ref(false);
function toggle() {
	if (expandable.value) open.value = !open.value;
}
</script>

<template>
	<div>
		<button
			class="flex items-center gap-1.5 text-sm transition-colors"
			:class="[
				open ? 'font-medium text-ink-gray-8' : 'text-ink-gray-5',
				expandable && !running && !open ? 'hover:text-ink-gray-7' : '',
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
			<!-- The open call's content sits in a bordered card so it can't bleed into
			the next block. Single: inputs directly; multiple: a connected timeline. -->
			<div
				v-if="open"
				class="mb-2 mt-1.5 rounded-lg border border-outline-gray-1 px-3 py-2.5"
			>
				<template v-if="single">
					<ArgsView :arguments="parts[0].arguments" />
					<ToolError
						v-if="error"
						:message="error"
						:class="{ 'mt-2': hasArgs(parts[0].arguments) }"
					/>
				</template>
				<div v-else>
					<ActivityStep
						v-for="(part, i) in parts"
						:key="part.id ?? i"
						:part="part"
						:number="i + 1"
						:last="i === parts.length - 1"
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
