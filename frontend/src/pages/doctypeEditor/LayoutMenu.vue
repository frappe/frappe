<!-- The layout crumb, named by the open layout, and the popover with the layout menu. -->
<template>
	<Popover v-model:open="shown" side="bottom" align="start" :auto-focus="false">
		<template #trigger="{ open: isOpen }">
			<button
				type="button"
				class="flex max-w-[360px] shrink-0 items-center gap-0.5 rounded-4 px-0.5 py-1 text-lg-medium leading-tighter text-ink-gray-9 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				:class="isOpen ? 'bg-surface-gray-3' : 'hover:bg-surface-gray-2'"
				data-layout-crumb
				@pointerenter="preload"
				@focus="preload"
			>
				<span class="min-w-0 truncate" :title="name">{{ name }}</span>
				<Icon name="lucide-chevron-down" class="size-4 shrink-0 text-ink-gray-5" />
			</button>
		</template>
		<LayoutMenuBody :canvas="canvas" @close="shown = false" />
	</Popover>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from "vue";
import { Icon, Popover } from "frappe-ui";
import type { DesignCanvas } from "./designCanvas";
import { openLayoutName } from "./layoutNames";

const props = defineProps<{ canvas: DesignCanvas }>();

const loadBody = () => import("./LayoutMenuBody.vue");
const LayoutMenuBody = defineAsyncComponent(loadBody);

const shown = ref(false);
const name = computed(() =>
	openLayoutName(props.canvas.openLayout.value, props.canvas.layout.value)
);

// Loads the menu's rows before the click opens it, so the popover never opens empty.
function preload() {
	loadBody().catch(() => undefined);
}
</script>
