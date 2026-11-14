<!-- The floating rail: the rail parked off screen in a box that slides in from the navigation's edge. -->
<template>
	<div
		ref="box"
		data-floating-rail
		:data-open="open"
		class="fixed inset-y-0 z-30 my-auto flex h-fit max-h-[calc(100vh-2rem)] flex-col overflow-hidden rounded-5 border border-outline-gray-2 bg-surface-base shadow-2xl transition-transform duration-200 ease-out motion-reduce:transition-none [&>[data-slot=sidebar-rail]]:h-auto [&>[data-slot=sidebar-rail]]:min-h-0 [&>[data-slot=sidebar-rail]]:shrink"
		:class="[
			navSide() === 'left' ? 'left-2' : 'right-2',
			open ? 'translate-x-0' : navSide() === 'left' ? CLOSED_LEFT : CLOSED_RIGHT,
		]"
	>
		<RailColumn
			:items="items"
			:context="context"
			:current="current"
			:chrome="!hasSidebar"
			:pin="canPin ? 'pin' : undefined"
			@pin="emit('pin')"
		/>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import type { NavigationItem } from "@/boot";
import type { ItemContext } from "@/navigation/types";
import { canPin } from "./navigationLayout";
import { navigationSide, navSide } from "./navigationSide";
import RailColumn from "./RailColumn.vue";
import { useEdgeReveal } from "./useEdgeReveal";

// Parked past its own width and the box's shadow.
const CLOSED_LEFT = "-translate-x-[calc(100%+3rem)]";
const CLOSED_RIGHT = "translate-x-[calc(100%+3rem)]";

defineProps<{
	items: NavigationItem[];
	context: ItemContext;
	current?: string;
	/** The page has a sidebar, which then carries the chrome; else the rail does. */
	hasSidebar: boolean;
}>();
const emit = defineEmits<{ pin: [] }>();

const box = ref<HTMLElement | null>(null);
// The page scrollbar is on the `end` side, in left-to-right and right-to-left pages alike.
const { open } = useEdgeReveal({
	side: navSide,
	scrollbarSide: () => navigationSide.value === "end",
	rail: box,
});
</script>
