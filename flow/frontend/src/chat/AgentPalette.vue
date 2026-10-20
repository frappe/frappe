<template>
	<PalettePanel
		title="Agents"
		back
		:query="query"
		:busy="query !== debounced"
		@close="emit('close')"
		@back="emit('back')"
	>
		<div class="flow-palette-list min-h-0 flex-1 overflow-y-auto p-1">
			<div v-if="locked" class="px-2 pb-1.5 pt-1 text-2xs text-ink-gray-5">
				The agent is fixed once the conversation starts.
			</div>
			<button
				v-for="agent in options"
				:key="agent.name"
				data-palette-item
				:aria-current="agent.name === current ? 'true' : undefined"
				:disabled="locked"
				class="flow-palette-row disabled:cursor-default"
				@click="choose(agent.name)"
			>
				<span class="min-w-0 truncate">
					{{ agent.title }}
				</span>
				<FeatherIcon
					v-if="agent.name === current"
					name="check"
					class="ml-auto h-4 w-4 flex-none"
				/>
			</button>
			<div v-if="!options.length" class="flow-palette-empty">No agents found</div>
		</div>
	</PalettePanel>
</template>

<script setup>
import { computed, inject, toRef } from "vue";
import FeatherIcon from "@flow/ui-core/components/FeatherIcon.vue";
import PalettePanel from "@flow/ui-core/components/PalettePanel.vue";
import { useDebouncedValue } from "@flow/ui-core/debounce.js";

import { useAgent } from "./agent.js";

// The agent a new chat starts with, chosen the way models are.
const props = defineProps({ query: { type: String, default: "" } }); // the composer's text after its "/"
const emit = defineEmits(["close", "back"]);
const page = inject("flowPage");
const { locked, current } = useAgent();

const debounced = useDebouncedValue(toRef(props, "query"), 150);
const options = computed(() => {
	const q = debounced.value.trim().toLowerCase();
	return page.state.boot.agents.filter((agent) => !q || agent.title.toLowerCase().includes(q));
});

function choose(name) {
	page.state.agent = name;
	emit("close");
}
</script>
