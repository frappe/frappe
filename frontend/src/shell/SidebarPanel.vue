<!--
  The panel a linked rail item opens, on frappe-ui's `Sidebar`. Nothing opens it by clicking: the
  address does. It collapses to nothing with the seam, through the shell's `toggle_sidebar` act.
-->
<template>
	<div class="group/sidebar relative flex h-full shrink-0">
		<!-- Bound, never `null`: left unset, `Sidebar` collapses itself below the `sm` breakpoint.
		     `border-0` while collapsed, or its 1px sits beside the content's and reads as 2px. -->
		<Sidebar
			:collapsed="collapsed"
			width="14rem"
			collapsedWidth="0px"
			:class="collapsed ? 'border-0' : 'border-l border-outline-gray-1'"
			:inert="collapsed"
		>
			<!-- 48px, no border: level with the page's header row, whose border stops at this panel's edge. -->
			<div class="flex h-12 shrink-0 items-center pl-4 pr-2">
				<p v-if="title" class="truncate text-base font-medium text-ink-gray-8">
					{{ title }}
				</p>
				<Button
					v-if="customizable"
					class="ml-auto"
					variant="ghost"
					icon="lucide-settings-2"
					:label="__('Customize this sidebar')"
					@click="emit('customize')"
				/>
			</div>

			<!-- `pt-0.5`: the first row's shadow is otherwise clipped on the viewport's top edge. -->
			<ScrollArea ref="scroller" class="min-h-0 flex-1" viewportClass="px-2 pb-2 pt-0.5">
				<nav class="flex flex-col gap-0.5" :aria-label="title">
					<!-- Keyed per sidebar: a section reused across sidebars replays its open/close transition. -->
					<SidebarRow
						v-for="node in tree"
						:key="`${address}:${node.item.key}`"
						:node="node"
						:context="context"
						:current="current"
						:sections="sections"
					/>
				</nav>
			</ScrollArea>
		</Sidebar>

		<SidebarEdge
			v-if="toggle"
			:open="!collapsed"
			:label="toggle.label!"
			@toggle="acts.perform(toggle.name)"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, useTemplateRef, watch } from "vue";
import { Button, ScrollArea, Sidebar } from "frappe-ui";
import { acts } from "@/acts/dispatcher";
import type { NavigationItem } from "@/boot";
import { __ } from "@/i18n";
import type { SectionMemory } from "@/navigation/sectionMemory";
import { useItemTree } from "@/navigation/useItemTree";
import type { ItemContext } from "@/navigation/types";
import { shellAct } from "./shellActs";
import SidebarEdge from "./SidebarEdge.vue";
import SidebarRow from "./SidebarRow.vue";

// `address` is the scrubbed key, which is also what the arrangement endpoints take for a `Sidebar`.
const props = defineProps<{
	address: string;
	items: NavigationItem[];
	context: ItemContext;
	title?: string;
	current?: string;
	sections?: SectionMemory;
	customizable?: boolean;
	collapsed: boolean;
}>();
const emit = defineEmits<{ customize: [] }>();

const toggle = computed(() => shellAct("toggle_sidebar"));

const tree = useItemTree(
	() => props.items,
	() => `the ${props.address} sidebar`
);

// Kept mounted across sidebars: without this, the next one opens at the last one's scroll offset.
const scroller = useTemplateRef<InstanceType<typeof ScrollArea>>("scroller");
watch(
	() => props.address,
	() => {
		const viewport = scroller.value?.viewportElement;
		if (viewport) viewport.scrollTop = 0;
	}
);
</script>
