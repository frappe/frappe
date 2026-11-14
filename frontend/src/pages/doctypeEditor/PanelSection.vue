<!-- One collapsible group of the field panel, as frappe/crm#3419's PanelSection. A closed group
     shows how many of its properties are set, so nothing set hides unseen. -->
<template>
	<div
		class="flex h-[42px] shrink-0 cursor-pointer select-none items-center gap-1.5 border-t border-outline-gray-1 px-4"
		@click="open = !open"
	>
		<button
			type="button"
			class="flex items-center gap-1 py-1 text-base font-semibold text-ink-gray-8"
			:aria-expanded="open"
			@click.stop="open = !open"
		>
			{{ label }}
			<span
				class="size-4 text-ink-gray-5"
				:class="open ? 'lucide-chevron-up' : 'lucide-chevron-down'"
				aria-hidden="true"
			/>
		</button>
		<span v-if="(!open || showCount) && count" class="text-sm text-ink-gray-4">{{
			count
		}}</span>
	</div>
	<div v-show="open" class="flex flex-col gap-2.5 px-4 pb-3 pt-1">
		<slot />
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { usePanelGroup } from "./panelIndex";

const props = withDefaults(
	defineProps<{ label: string; startOpen?: boolean; count?: number; showCount?: boolean }>(),
	{ startOpen: true, count: 0, showCount: false },
);
const open = ref(props.startOpen);
usePanelGroup(() => props.label, open);
</script>
