<!-- A panel row's label: truncates to one line, marks a required field and explains itself on hover or tap. -->
<template>
	<Popover v-if="tipped && coarse" side="bottom" align="start" :auto-focus="false">
		<template #trigger>
			<span class="flex h-7 min-w-0 text-base leading-7 text-ink-gray-5">
				<span ref="text" class="truncate">{{ field.label }}</span>
				<span v-if="field.reqd" class="ms-0.5 shrink-0 text-ink-red-4" aria-hidden="true"
					>*</span
				>
			</span>
		</template>
		<div class="px-2 py-1 text-xs">
			<PanelLabelTip
				:field="field"
				class="text-ink-gray-8"
				description-class="text-ink-gray-5"
			/>
		</div>
	</Popover>
	<Tooltip v-else :disabled="!tipped" :hover-delay="500">
		<span class="flex h-7 min-w-0 text-base leading-7 text-ink-gray-5">
			<span ref="text" class="truncate">{{ field.label }}</span>
			<span v-if="field.reqd" class="ms-0.5 shrink-0 text-ink-red-4" aria-hidden="true"
				>*</span
			>
		</span>
		<template #content>
			<PanelLabelTip :field="field" description-class="text-ink-gray-4" />
		</template>
	</Tooltip>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useMediaQuery, useResizeObserver } from "@vueuse/core";
import { Popover, Tooltip } from "frappe-ui";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import PanelLabelTip from "./PanelLabelTip.vue";

const props = defineProps<{ field: FieldNode }>();

const coarse = useMediaQuery("(pointer: coarse)");
const text = ref<HTMLElement | null>(null);
const truncated = ref(false);
// A tip shows only when it tells more than the label already does.
const tipped = computed(() => truncated.value || !!props.field.description);

function measure() {
	const label = text.value;
	truncated.value = !!label && label.scrollWidth > label.clientWidth;
}

onMounted(measure);
useResizeObserver(text, measure);
watch(
	() => props.field.label,
	() => nextTick(measure)
);
</script>
