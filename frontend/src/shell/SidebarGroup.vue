<!-- One rail item that opens a sidebar, as a group in the sidebar-only layout: its header, then the sidebar's rows. -->
<template>
	<div :data-key="item.key" :data-sidebar="address">
		<button
			:id="headerId"
			type="button"
			:class="HEADER"
			:aria-expanded="open"
			@click="emit('toggle')"
		>
			<span class="grid shrink-0 place-items-center"><Icon :name="iconOf(item)" /></span>
			<span class="ml-2 min-w-0 flex-1 truncate text-sm">{{ labelOf(item, context) }}</span>
			<span
				class="lucide-chevron-right mr-1 size-4 shrink-0 text-ink-gray-5 transition-transform"
				:class="open ? 'rotate-90' : 'rtl:-scale-x-100'"
				aria-hidden="true"
			/>
		</button>

		<!-- Mounted only while open, as a section's children are. -->
		<div
			v-if="open"
			role="group"
			:aria-labelledby="headerId"
			class="ml-3 mt-0.5 flex flex-col gap-0.5 border-l border-outline-gray-2 pl-1"
		>
			<!-- Keyed per sidebar: a section reused across sidebars replays its open/close transition. -->
			<SidebarRow
				v-for="node in tree"
				:key="`${address}:${node.item.key}`"
				:node="node"
				:context="rowContext"
				:current="current"
				:sections="sections"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { useId } from "vue";
import type { NavigationItem } from "@/boot";
import Icon from "@/icons/Icon.vue";
import { iconOf, labelOf } from "@/navigation/registry";
import type { SectionMemory } from "@/navigation/sectionMemory";
import type { ItemContext } from "@/navigation/types";
import { useItemTree } from "@/navigation/useItemTree";
import SidebarRow from "./SidebarRow.vue";

// `SidebarRow`'s own look for a row with a target, so a group header sits level with its siblings.
const HEADER =
	"flex h-7 w-full items-center rounded-4 pl-2 text-left text-ink-gray-6 transition hover:bg-surface-gray-2 focus-visible:ring-0 focus-visible:focus-ring";

const props = defineProps<{
	item: NavigationItem;
	/** The rail's context: it names the header. */
	context: ItemContext;
	address: string;
	rows: NavigationItem[];
	rowContext: ItemContext;
	sections?: SectionMemory;
	/** The row inside the sidebar to highlight. */
	current?: string;
	open: boolean;
}>();
const emit = defineEmits<{ toggle: [] }>();

const headerId = useId();
const tree = useItemTree(
	() => props.rows,
	() => `the ${props.address} sidebar`
);
</script>
