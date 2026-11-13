<!-- The 380px panel beside the Design canvas: the selected field's settings, or the selected tab's,
     section's or column's. -->
<template>
	<aside
		class="flex w-[380px] shrink-0 flex-col overflow-y-auto border-l border-outline-gray-1"
		data-editor-panel
	>
		<FieldPanel
			v-if="canvas.selectedField.value"
			:key="canvas.selectedField.value.fieldname"
			:canvas="canvas"
			:field="canvas.selectedField.value"
		/>
		<ContainerPanel
			v-else-if="container"
			:key="JSON.stringify(container)"
			:canvas="canvas"
			:selection="container"
		/>
		<p v-else class="px-4 py-6 text-base text-ink-gray-5">
			{{ __("Select a field, section or tab to edit it.") }}
		</p>
	</aside>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { __ } from "@/i18n";
import ContainerPanel from "./ContainerPanel.vue";
import type { DesignCanvas } from "./designCanvas";
import FieldPanel from "./FieldPanel.vue";

const props = defineProps<{ canvas: DesignCanvas }>();

const container = computed(() => {
	const selection = props.canvas.selection.value;
	return selection && selection.kind !== "field" ? selection : null;
});
</script>
