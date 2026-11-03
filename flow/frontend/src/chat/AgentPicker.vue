<template>
	<span class="relative min-w-0">
		<!-- its list hangs from it -->
		<Tooltip :text="`Agent: ${title}`" :disabled="open">
			<Button
				ref="trigger"
				variant="ghost"
				size="md"
				icon="lucide-brain-cog"
				:data-state="open ? 'active' : undefined"
				:aria-label="`Agent: ${title}`"
				:aria-expanded="open"
				@click="open ? close() : show()"
			/>
		</Tooltip>
		<PalettePanel
			v-if="open"
			:title="`Agent: ${title}`"
			dropdown
			align="left"
			:width="264"
			:query="search"
			@close="close"
		>
			<div class="flex flex-none pl-1 pr-2.5 pt-1">
				<input
					ref="field"
					v-model="search"
					placeholder="Search agents…"
					class="h-8 min-w-0 flex-1 border-0 bg-transparent px-2 text-base text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:ring-0"
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
	</span>
</template>

<script setup>
import { computed, inject, nextTick, ref } from "vue";
import { Button, Tooltip } from "frappe-ui";
import PalettePanel from "@flow/ui-core/components/PalettePanel.vue";
import { layout } from "@flow/ui-core/layout.js";

import { useAgent } from "./agent.js";

// A new chat's agent, over the composer, picked from its own list.
const page = inject("flowPage");
const { current, title } = useAgent();
const open = ref(false);
const search = ref("");
const trigger = ref(null);
const field = ref(null);

// matched by every word of the search in their title
const options = computed(() => {
	const words = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
	return page.state.boot.agents.filter((agent) =>
		words.every((word) => agent.title.toLowerCase().includes(word))
	);
});

function show() {
	search.value = "";
	open.value = true;
	// a phone's list leaves its search for a tap, rather than raise the keyboard over it
	nextTick(() => layout.phone || field.value?.focus());
}

function close() {
	open.value = false;
	nextTick(() => trigger.value?.$el?.focus());
}

function choose(name) {
	page.state.agent = name;
	close();
}
</script>
