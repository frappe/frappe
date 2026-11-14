<!--
  The navigation in the sidebar-only layout: no rail. Each rail item that opens a sidebar is a group
  with that sidebar's rows under it; any other rail item is one row. 15rem wide, in the `#sidebar` slot.
-->
<template>
	<!-- Bound, never `null`: left unset, `Sidebar` collapses itself below the `sm` breakpoint. -->
	<Sidebar :collapsed="false" :width="width" class="border-0">
		<NavigationHeader />

		<ScrollArea class="min-h-0 flex-1" viewportClass="px-2 pb-2 pt-0.5">
			<nav class="flex flex-col gap-0.5" :aria-label="appTitle">
				<template v-for="{ node, address } in entries" :key="node.item.key">
					<SidebarGroup
						v-if="address"
						:item="node.item"
						:context="context"
						:address="address"
						:rows="sidebars[address]"
						:row-context="contexts.sidebars[address]"
						:sections="sections[address]"
						:current="current.sidebar === address ? current.rowKey : undefined"
						:open="isOpen(node.item.key)"
						@toggle="toggle(node.item.key)"
					/>
					<SidebarRow
						v-else
						:node="node"
						:context="context"
						:current="current.railKey"
					/>
				</template>
			</nav>
		</ScrollArea>

		<div class="flex h-12 shrink-0 items-center border-t border-outline-gray-1 px-2">
			<UserMenu wide />
		</div>
	</Sidebar>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from "vue";
import { ScrollArea, Sidebar } from "frappe-ui";
import type { NavigationItem } from "@/boot";
import type { CurrentNavigation, NavigationContexts } from "@/navigation/current";
import { renderingOf } from "@/navigation/registry";
import type { SectionMemory } from "@/navigation/sectionMemory";
import { useItemTree } from "@/navigation/useItemTree";
import { useAppMenu } from "./appMenu";
import NavigationHeader from "./NavigationHeader.vue";
import SidebarGroup from "./SidebarGroup.vue";
import SidebarRow from "./SidebarRow.vue";
import UserMenu from "./UserMenu.vue";

const props = withDefaults(
	defineProps<{
		items: NavigationItem[];
		contexts: NavigationContexts;
		sidebars: Record<string, NavigationItem[]>;
		sections: Record<string, SectionMemory>;
		current: CurrentNavigation;
		width?: string;
	}>(),
	{ width: "15rem" }
);

const { appTitle } = useAppMenu();
const context = computed(() => props.contexts.rail);

// The rail is flat, so these are its items in order.
const tree = useItemTree(() => props.items, "the rail");

// `address` is the sidebar a rail item opens, when that sidebar has rows to show.
const entries = computed(() =>
	tree.value.map((node) => {
		const rendering = renderingOf(node.item, context.value);
		const address = rendering && "sidebar" in rendering ? rendering.sidebar : undefined;
		return { node, address: address && props.sidebars[address]?.length ? address : undefined };
	})
);

// A reader's own opens and closes, for this page's session. A group with no entry follows the address.
const toggled = reactive<Record<string, boolean>>({});

function isOpen(key: string): boolean {
	return toggled[key] ?? key === props.current.railKey;
}

function toggle(key: string) {
	toggled[key] = !isOpen(key);
}

// Arriving in a group opens it, even if the reader shut it earlier.
watch(
	() => props.current.railKey,
	(key) => key && delete toggled[key]
);
</script>
