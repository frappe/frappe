<!-- A Table or Table MultiSelect field's rows in the field panel: its child table, the jump to the
     child's own editor, where its fields and grid columns are edited, and a Table's grid columns. -->
<template>
	<PanelRow :label="__('Child table')">
		<ChildTablePicker :canvas="canvas" :field="field" />
	</PanelRow>
	<PanelRow v-if="field.options" :label="__('Fields')" :box="false">
		<button
			type="button"
			class="flex h-7 w-full min-w-0 items-center gap-1 rounded-4 px-2 text-left text-base text-ink-gray-8 hover:bg-surface-gray-2"
			data-open-child
			@click="acts.perform('fields.open_child', field.fieldname)"
		>
			<span class="truncate">{{ __("Edit {0}", [field.options]) }}</span>
			<span
				class="lucide-arrow-up-right size-4 shrink-0 text-ink-gray-5"
				aria-hidden="true"
			/>
		</button>
	</PanelRow>
	<PanelRow
		v-if="field.fieldtype === 'Table' && field.options && childFields"
		:label="__('Grid')"
		:box="false"
	>
		<p class="px-2 py-1 text-base leading-5 text-ink-gray-6" data-grid-summary>
			{{ columns || __("No columns yet") }}
		</p>
	</PanelRow>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { useChildFields } from "./childFields";
import ChildTablePicker from "./ChildTablePicker.vue";
import type { DesignCanvas } from "./designCanvas";
import { gridColumnsOf } from "./gridColumns";
import PanelRow from "./PanelRow.vue";

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();

const childFields = useChildFields(() => props.field.options);
const columns = computed(() => {
	const fields = childFields.value;
	if (!fields) return "";
	return gridColumnsOf(fields)
		.map((field) => __(field.label || field.fieldname))
		.join(", ");
});
</script>
