<!-- One body column as the row draws it: its width or its flex share, its own scroll
     container, and a strip when the reader shut it. -->
<template>
	<div
		class="flex min-h-0 flex-col overflow-hidden"
		:class="[
			fixed ? 'shrink-0' : 'min-w-0 flex-1',
			separator ? 'border-l border-outline-gray-1' : '',
			dragging || !fixed ? '' : 'transition-[width] duration-300 ease-in-out',
		]"
		:style="
			fixed ? { width: `${column.collapsed ? STRIP_WIDTH : column.width}px` } : undefined
		"
		:data-body-column="column.item.name"
		:data-collapsed="strip ? '' : undefined"
		@transitionend.self="onTransitionEnd"
	>
		<div
			class="min-h-0 flex-1 overflow-y-auto"
			:class="strip || column.item.gutter === false ? '' : pageGutter"
			:style="column.bounds && !strip ? { width: `${column.width}px` } : undefined"
		>
			<slot :collapsed="strip" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { STRIP_WIDTH, type BodyColumn } from "@/recordPage";
import { pageGutter } from "@/shell/PageFrame.vue";

const props = defineProps<{ column: BodyColumn; separator: boolean; dragging: boolean }>();

// The content stays mounted while the width shrinks over it, as it does when it grows.
// The timer matches `duration-300`, for a DOM that fires no transitionend.
const CLOSE_DURATION = 300;
const closing = ref(false);
let settle: ReturnType<typeof setTimeout> | undefined;

const strip = computed(() => props.column.collapsed && !closing.value);
// A shut flex column is a 48px strip, so it takes a fixed width while it is shut.
const fixed = computed(() => props.column.bounds !== null || props.column.collapsed);

watch(
	() => props.column.collapsed,
	(value) => {
		clearTimeout(settle);
		closing.value = value;
		if (value) settle = setTimeout(settled, CLOSE_DURATION);
	}
);

onBeforeUnmount(() => clearTimeout(settle));

function onTransitionEnd(event: TransitionEvent) {
	if (event.propertyName === "width") settled();
}

function settled() {
	clearTimeout(settle);
	closing.value = false;
}
</script>
