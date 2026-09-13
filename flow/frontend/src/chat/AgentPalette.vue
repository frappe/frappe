<template>
	<PalettePanel title="Agents" back @close="emit('close')" @back="emit('back')">
		<template #search>
			<PaletteSearch v-model="query" placeholder="Search agents" autofocus />
		</template>

		<div class="min-h-0 flex-1 overflow-y-auto p-1.5">
			<div v-if="locked" class="px-2.5 pb-1.5 pt-1 text-2xs text-ink-gray-5">
				The agent is fixed once the conversation starts.
			</div>
			<button
				v-for="agent in options"
				:key="agent.name"
				data-palette-item
				:aria-current="agent.name === current ? 'true' : undefined"
				:disabled="locked"
				class="flex w-full items-center gap-2.5 rounded-5 px-2.5 py-2 text-left enabled:hover:bg-surface-gray-2 disabled:cursor-default"
				@click="choose(agent.name)"
			>
				<span
					class="min-w-0 flex-1 truncate text-xs font-medium leading-4 text-ink-gray-9"
				>
					{{ agent.title }}
				</span>
				<FeatherIcon
					v-if="agent.name === current"
					name="check"
					class="h-4 w-4 flex-none text-ink-gray-7"
				/>
			</button>
			<div v-if="!options.length" class="px-3 py-8 text-center text-xs text-ink-gray-5">
				No agents found
			</div>
		</div>
	</PalettePanel>
</template>

<script setup>
import { computed, inject, ref } from "vue";
import FeatherIcon from "@flow/ui-core/components/FeatherIcon.vue";
import PalettePanel from "@flow/ui-core/components/PalettePanel.vue";
import PaletteSearch from "@flow/ui-core/components/PaletteSearch.vue";
import { useDebouncedValue } from "@flow/ui-core/debounce.js";

import { useAgent } from "./agent.js";

// The agent a new chat starts with, chosen the way models are.
const emit = defineEmits(["close", "back"]);
const page = inject("flowPage");
const { locked, current } = useAgent();

const query = ref("");
const debounced = useDebouncedValue(query, 150);
const options = computed(() => {
	const q = debounced.value.trim().toLowerCase();
	return page.state.boot.agents.filter((agent) => !q || agent.title.toLowerCase().includes(q));
});

function choose(name) {
	page.state.agent = name;
	emit("close");
}
</script>
