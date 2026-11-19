<!-- The mark an agent's relay calls raise at the foot of the tab: who is driving, and Stop. Mounted by the relay on its first call. -->
<template>
	<Transition
		enter-active-class="transition-opacity duration-200 motion-reduce:transition-none"
		leave-active-class="transition-opacity duration-200 motion-reduce:transition-none"
		enter-from-class="opacity-0"
		leave-to-class="opacity-0"
	>
		<div
			v-if="mark.state.value !== 'hidden'"
			class="fixed bottom-[calc(4rem+var(--shell-nav-inset-bottom,0px))] left-1/2 z-30 flex max-w-[calc(100vw-2rem)] -translate-x-1/2 items-center gap-2 min-h-[38px] rounded-full border border-outline-gray-3 bg-surface-base py-1 ps-3 shadow-2xl"
			:class="stopped ? 'pe-3' : 'pe-1'"
			data-agent-mark
		>
			<span
				v-if="!stopped"
				class="size-2 shrink-0 rounded-full"
				:class="
					mark.state.value === 'running'
						? 'animate-pulse bg-surface-gray-7 motion-reduce:animate-none'
						: 'border-2 border-outline-gray-5'
				"
				aria-hidden="true"
			/>
			<span role="status" class="truncate text-base text-ink-gray-8" :title="text">{{
				text
			}}</span>
			<Button
				v-if="!stopped"
				class="rounded-full"
				size="sm"
				variant="subtle"
				:label="__('Stop')"
				@click="mark.stop()"
			/>
		</div>
	</Transition>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { computed } from "vue";
import { __ } from "@/i18n";
import type { AgentMark } from "./agentMark";

const props = defineProps<{ mark: AgentMark }>();

const stopped = computed(() => props.mark.state.value === "stopped");
const text = computed(() =>
	stopped.value
		? __("Stopped. Reload to allow agents again.")
		: __("{0} is driving this tab", [props.mark.client.value || __("An agent")])
);
</script>
