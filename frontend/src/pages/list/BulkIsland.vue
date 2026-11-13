<!-- Where the bulk bar floats: a zero-height strip between the rows and the footer, so the bar sits over the last rows. -->
<template>
	<div class="relative h-0 shrink-0">
		<div ref="sizer" class="absolute inset-x-4" />
		<div
			v-if="open"
			class="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-24 bg-[linear-gradient(to_top,var(--surface-base)_30%,transparent)]"
		/>
		<Transition
			enter-active-class="transition duration-150 ease-out"
			enter-from-class="translate-y-2 opacity-0"
			leave-active-class="transition duration-100 ease-in"
			leave-to-class="translate-y-2 opacity-0"
		>
			<div
				v-if="open"
				class="absolute inset-x-0 bottom-4 z-20 mx-auto w-max max-w-[calc(100%-2rem)]"
			>
				<BulkBar v-bind="$attrs" :room="room" />
			</div>
		</Transition>
	</div>
</template>

<script setup lang="ts">
import { useElementSize } from "@vueuse/core";
import { ref } from "vue";
import BulkBar from "./BulkBar.vue";

defineOptions({ inheritAttrs: false });
defineProps<{ open: boolean }>();
// The sizer's inset-x-4 must match the wrapper's max-w calc: the bar fits itself to the sizer.
const sizer = ref<HTMLElement | null>(null);
const { width: room } = useElementSize(sizer);
</script>
