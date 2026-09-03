<!--
  The panel a linked rail item opens. Nothing opens it by clicking: the address does, read back by
  `navigation/current.ts`. An empty sidebar is absent from the payload, so no empty panel exists.
-->
<template>
	<aside class="flex w-56 shrink-0 flex-col gap-1 border-r border-outline-gray-2 p-2">
		<p v-if="title" class="truncate px-2 py-1.5 text-sm font-medium text-ink-gray-8">
			{{ title }}
		</p>

		<ul class="overflow-y-auto">
			<NavigationRow
				v-for="node in tree"
				:key="node.item.key"
				:node="node"
				:context="context"
				:current="current"
				:reserve="reserve"
				:sections="sections"
			/>
		</ul>

		<button
			v-if="arrangeable"
			class="mt-auto rounded px-2 py-1 text-left text-xs text-ink-gray-5 hover:bg-surface-gray-2"
			@click="emit('arrange')"
		>
			Arrange
		</button>
	</aside>
</template>

<script setup lang="ts">
import type { NavigationItem } from "@/boot";
import NavigationRow from "@/navigation/NavigationRow.vue";
import type { SectionMemory } from "@/navigation/sectionMemory";
import { useItemTree } from "@/navigation/useItemTree";
import { useIconSlot } from "@/navigation/iconSlot";
import type { ItemContext } from "@/navigation/types";

// `address` is the scrubbed key, which is also what the arrangement endpoints take for a `Sidebar`.
const props = defineProps<{
	address: string;
	items: NavigationItem[];
	context: ItemContext;
	title?: string;
	current?: string;
	sections?: SectionMemory;
	arrangeable?: boolean;
}>();
const emit = defineEmits<{ arrange: [] }>();

const tree = useItemTree(
	() => props.items,
	() => `the ${props.address} sidebar`
);

const reserve = useIconSlot(
	() => props.items,
	() => props.context
);
</script>
