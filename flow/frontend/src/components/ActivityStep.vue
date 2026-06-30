<script setup>
import { computed, ref } from "vue";
import { FeatherIcon, Spinner } from "@/lib/ui";
import ActivityLabel from "./ActivityLabel.vue";
import ArgsView from "./ArgsView.vue";
import { toolLabel, argEntries } from "@/lib/toolMeta";

// One timeline step. `live` is false after the run ends, so an interrupted tool
// (no result) shows a static node, not a spinner.
const props = defineProps({
	part: { type: Object, required: true },
	live: { type: Boolean, default: false },
});

const active = computed(
	() => props.live && props.part.result === null && props.part.approval === null
);
const label = computed(() => toolLabel(props.part.name));

const hasDetail = computed(() => argEntries(props.part.arguments).length > 0);
const open = ref(false);
function toggle() {
	if (hasDetail.value) open.value = !open.value;
}
</script>

<template>
	<div class="relative py-1 pl-5">
		<!-- Shared node, masking the connector so the line reads as linking nodes. -->
		<span
			class="absolute left-0 top-2 flex w-3.5 justify-center bg-surface-white text-ink-gray-4"
			aria-hidden="true"
		>
			<Spinner v-if="active" class="h-3 w-3" />
			<span v-else class="mt-0.5 h-1.5 w-1.5 rounded-full bg-ink-gray-4"></span>
		</span>

		<button
			class="flex w-full items-center gap-1.5 text-left text-sm text-ink-gray-6 transition-colors"
			:class="hasDetail ? 'hover:text-ink-gray-8' : 'cursor-default'"
			@click="toggle"
		>
			<ActivityLabel :text="label" :active="active" />
			<span class="flex-1"></span>
			<FeatherIcon
				v-if="hasDetail"
				name="chevron-right"
				class="h-3.5 w-3.5 shrink-0 text-ink-gray-4 transition-transform"
				:class="{ 'rotate-90': open }"
			/>
		</button>

		<div v-if="open && hasDetail" class="mb-1 mt-1.5">
			<ArgsView :arguments="part.arguments" />
		</div>
	</div>
</template>
