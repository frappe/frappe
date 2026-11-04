<template>
	<!-- a new chat's agent, beside the composer's + menu -->
	<PalettePanel
		title="Agent"
		dropdown
		align="left"
		:beside="beside"
		:width="264"
		:query="search"
		@close="emit('close')"
	>
		<div class="flex flex-none pl-1 pr-2.5 pt-1">
			<input
				ref="field"
				v-model="search"
				placeholder="Search agents…"
				class="h-8 min-w-0 flex-1 border-0 bg-transparent px-[11px] text-base text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
			/>
		</div>
		<div class="flow-palette-list min-h-0 flex-1 overflow-y-auto p-1">
			<button
				v-for="agent in options"
				:key="agent.name"
				data-palette-item
				:aria-current="agent.name === current ? 'true' : undefined"
				class="flow-palette-row"
				@click="choose(agent.name)"
			>
				<span class="min-w-0 truncate">{{ agent.title }}</span>
				<span
					v-if="agent.name === current"
					class="lucide-check ml-auto size-4 flex-none"
					aria-hidden="true"
				/>
			</button>
			<div v-if="!options.length" class="flow-palette-empty">No matching agents</div>
		</div>
	</PalettePanel>
</template>

<script setup>
import { computed, inject, onMounted, ref } from "vue";
import PalettePanel from "@flow/ui-core/components/PalettePanel.vue";
import { layout } from "@flow/ui-core/layout.js";

import { useAgent } from "./agent.js";

// A new chat's agent, picked from its own list beside the composer's + menu.
defineProps({ beside: { type: Number, default: 0 } }); // this far from the + button's left
const emit = defineEmits(["close"]);
const page = inject("flowPage");
const { current } = useAgent();
const search = ref("");
const field = ref(null);

// matched by every word of the search in their title
const options = computed(() => {
	const words = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
	return page.state.boot.agents.filter((agent) =>
		words.every((word) => agent.title.toLowerCase().includes(word))
	);
});

// a phone's list leaves its search for a tap, rather than raise the keyboard over it
onMounted(() => layout.phone || field.value?.focus());

function choose(name) {
	page.state.agent = name;
	emit("close");
}
</script>
