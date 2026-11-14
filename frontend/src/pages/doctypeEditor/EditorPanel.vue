<!-- The 380px panel beside the Design canvas: the selected field's settings, or the selected tab's,
     section's or column's; with nothing selected, the field types to add, and outside Details the fields to place. -->
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
		<PanelTray
			v-else-if="takesOff(canvas)"
			:key="canvas.openLayout.value.type"
			:canvas="canvas"
		/>
		<template v-else>
			<p class="flex min-h-[42px] items-center px-4 py-2 text-p-sm text-ink-gray-5">
				{{ __("Select a field or a section heading to edit it here.") }}
			</p>
			<GridColumnsGroup
				v-if="canvas.state.definition.istable"
				:key="canvas.state.doctype"
				:canvas="canvas"
			/>
			<NewFieldTypes :canvas="canvas" :label="__('Add a field')" />
		</template>
	</aside>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { __ } from "@/i18n";
import ContainerPanel from "./ContainerPanel.vue";
import type { DesignCanvas } from "./designCanvas";
import { takesOff } from "./fieldPanel";
import FieldPanel from "./FieldPanel.vue";
import GridColumnsGroup from "./GridColumnsGroup.vue";
import NewFieldTypes from "./NewFieldTypes.vue";
import PanelTray from "./PanelTray.vue";

const props = defineProps<{ canvas: DesignCanvas }>();

const container = computed(() => {
	const selection = props.canvas.selection.value;
	return selection && selection.kind !== "field" ? selection : null;
});
</script>
