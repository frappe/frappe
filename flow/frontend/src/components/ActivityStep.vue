<script setup>
import { computed, ref } from "vue";
import { FeatherIcon, Spinner } from "@/lib/ui";
import ActivityLabel from "./ActivityLabel.vue";
import ArgsView from "./ArgsView.vue";
import ToolError from "./ToolError.vue";
import { toolLabel, toolContext, hasArgs, blockKeysFor, toolError } from "@/lib/toolMeta";
import { __ } from "@/lib/translate";

// One timeline step. A fixed-width gutter holds the dot; connector lines are
// flex-1 fillers above and below it, so they auto-centre on the dot and meet the
// neighbouring steps whatever the label's height — no hardcoded offsets.
const props = defineProps({
	part: { type: Object, required: true },
	number: { type: Number, required: true },
	last: { type: Boolean, default: false },
	live: { type: Boolean, default: false },
});

const active = computed(
	() => props.live && props.part.result === null && props.part.approval === null
);
const label = computed(() => toolLabel(props.part.name));
const context = computed(() => toolContext(props.part.arguments));
const error = computed(() => toolError(props.part.result));
const expandable = computed(() => hasArgs(props.part.arguments) || Boolean(error.value));
const blockKeys = computed(() => blockKeysFor(props.part.name));

const open = ref(false);
function toggle() {
	if (expandable.value) open.value = !open.value;
}
</script>

<template>
	<div>
		<div class="flex gap-2.5">
			<!-- Gutter: filler line, dot, filler line — flex-1 fillers centre the dot
			     and the visible ones connect to the steps above/below. -->
			<div class="flex w-5 shrink-0 flex-col items-center">
				<span class="w-px flex-1" :class="{ 'bg-surface-gray-3': number > 1 }"></span>
				<span
					class="z-[1] flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-outline-gray-1 bg-surface-white"
				>
					<Spinner v-if="active" class="h-3 w-3 text-ink-gray-5" />
					<span v-else class="text-[10px] leading-none tabular-nums text-ink-gray-4">
						{{ number }}
					</span>
				</span>
				<span class="w-px flex-1" :class="{ 'bg-surface-gray-3': !last }"></span>
			</div>
			<button
				class="flex min-w-0 flex-1 items-center gap-2.5 py-2 text-left"
				:class="expandable ? '' : 'cursor-default'"
				@click="toggle"
			>
				<ActivityLabel
					:text="label"
					:active="active"
					class="text-sm font-medium text-ink-gray-8"
				/>
				<span v-if="context" class="truncate text-xs text-ink-gray-4"
					>· {{ context }}</span
				>
				<span v-if="error" class="shrink-0 text-xs text-ink-gray-5"
					>· {{ __("Failed") }}</span
				>
				<span class="flex-1"></span>
				<FeatherIcon
					v-if="expandable"
					name="chevron-right"
					class="h-3.5 w-3.5 shrink-0 text-ink-gray-4 transition-transform"
					:class="{ 'rotate-90': open }"
				/>
			</button>
		</div>

		<div v-if="open && expandable" class="flex gap-2.5">
			<div class="flex w-5 shrink-0 justify-center">
				<span class="w-px" :class="{ 'bg-surface-gray-3': !last }"></span>
			</div>
			<div class="min-w-0 flex-1 pb-2">
				<ArgsView :arguments="part.arguments" :block-keys="blockKeys" />
				<ToolError
					v-if="error"
					:message="error"
					:class="{ 'mt-2': hasArgs(part.arguments) }"
				/>
			</div>
		</div>
	</div>
</template>
