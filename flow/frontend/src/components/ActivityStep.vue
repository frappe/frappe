<script setup>
import { computed, ref } from "vue";
import { FeatherIcon, Spinner } from "@/lib/ui";
import ActivityLabel from "./ActivityLabel.vue";
import ArgsView from "./ArgsView.vue";
import { toolLabel, toolContext, hasArgs } from "@/lib/toolMeta";

// One timeline step. The circle sits in the same items-center row as the label,
// so they stay vertically aligned whatever the label's height. Connector segments
// meet the circle's edges; the last step draws none, so the line never overruns.
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
const expandable = computed(() => hasArgs(props.part.arguments));

const open = ref(false);
function toggle() {
	if (expandable.value) open.value = !open.value;
}
</script>

<template>
	<div class="relative">
		<!-- Rail: segments run in the circle's centre column (x≈9.5px), meeting its
		     top (8px) and bottom (28px) edges. -->
		<span
			v-if="number > 1"
			class="absolute left-[9.5px] top-0 h-2 w-px bg-surface-gray-3"
		></span>
		<span
			v-if="!last"
			class="absolute bottom-0 left-[9.5px] top-7 w-px bg-surface-gray-3"
		></span>

		<button
			class="flex w-full items-center gap-2.5 py-2 text-left"
			:class="expandable ? '' : 'cursor-default'"
			@click="toggle"
		>
			<span
				class="relative z-[1] flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-outline-gray-1 bg-surface-white"
			>
				<Spinner v-if="active" class="h-3 w-3 text-ink-gray-5" />
				<span v-else class="text-[10px] leading-none tabular-nums text-ink-gray-4">
					{{ number }}
				</span>
			</span>
			<ActivityLabel
				:text="label"
				:active="active"
				class="text-sm font-medium text-ink-gray-8"
			/>
			<span v-if="context" class="truncate text-xs text-ink-gray-4">· {{ context }}</span>
			<span class="flex-1"></span>
			<FeatherIcon
				v-if="expandable"
				name="chevron-right"
				class="h-3.5 w-3.5 shrink-0 text-ink-gray-4 transition-transform"
				:class="{ 'rotate-90': open }"
			/>
		</button>

		<div v-if="open && expandable" class="mb-2 ml-[30px]">
			<ArgsView :arguments="part.arguments" />
		</div>
	</div>
</template>
