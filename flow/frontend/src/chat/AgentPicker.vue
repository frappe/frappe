<template>
	<button
		class="flex h-7 min-w-0 max-w-[240px] items-center rounded-5 px-2 text-xs font-medium text-ink-gray-7 enabled:hover:bg-surface-gray-2 disabled:cursor-default"
		:title="locked ? 'The agent is fixed once the conversation starts' : 'Agent'"
		:disabled="locked"
		@click="emit('open', 'agents')"
	>
		<span class="min-w-0 truncate">{{ title }}</span>
	</button>
</template>

<script setup>
import { useAgent } from "./agent.js";

// Names the agent in force; opens the agent palette above the composer.
const emit = defineEmits(["open"]);
const { locked, title } = useAgent();
</script>
