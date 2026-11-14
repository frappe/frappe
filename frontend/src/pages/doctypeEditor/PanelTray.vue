<!-- The panel outside Details with nothing selected: the fields this layout leaves off, then "New
     field" types. A click places or adds at the end of the section in view, on this layout only. -->
<template>
	<p class="flex min-h-[42px] items-center px-4 py-2 text-p-sm text-ink-gray-6">
		{{ __("Select a field or a section heading to edit it here.") }}
	</p>
	<div class="flex flex-col" data-panel-tray>
		<PanelSection :label="__('Fields not on this layout')" :count="rows.length" show-count>
			<TextInput
				v-model="fieldQuery"
				:placeholder="__('Find a field')"
				data-panel-tray-search
			>
				<template #prefix
					><Icon name="lucide-search" class="size-4 text-ink-gray-5"
				/></template>
			</TextInput>
			<div v-if="shownRows.length" class="-mx-2 flex max-h-[272px] flex-col overflow-y-auto">
				<ItemListRow
					v-for="row in shownRows"
					:key="row.field.fieldname"
					as="button"
					type="button"
					class="!min-h-8 shrink-0 text-left hover:bg-surface-gray-2"
					:data-panel-tray-field="row.field.fieldname"
					@click="place(row.field.fieldname)"
				>
					<template #prefix>
						<Icon
							:name="typeIcon(typeName(row.field.fieldtype, row.field.options))"
							class="size-4 text-ink-gray-5"
						/>
					</template>
					<span class="block truncate text-ink-gray-8">{{ label(row.field) }}</span>
					<template #suffix>
						<span class="flex items-center gap-1.5">
							<Badge v-if="row.new" theme="gray" :label="__('New since the save')" />
							<Badge
								v-if="row.asked"
								theme="gray"
								:label="__('Asked for on save')"
							/>
							<span class="max-w-28 truncate text-sm text-ink-gray-4">{{
								__(row.field.fieldtype)
							}}</span>
						</span>
					</template>
				</ItemListRow>
			</div>
			<p v-else class="text-p-sm text-ink-gray-5">
				{{
					rows.length
						? __("No field matches.")
						: __("Every field of the DocType is on this layout.")
				}}
			</p>
		</PanelSection>
	</div>
	<NewFieldTypes :canvas="canvas" :label="__('New field')" />
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Badge, Icon, ItemListRow, TextInput } from "frappe-ui";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { typeIcon, typeName } from "./fieldtypes";
import NewFieldTypes from "./NewFieldTypes.vue";
import PanelSection from "./PanelSection.vue";

const props = defineProps<{ canvas: DesignCanvas }>();

const fieldQuery = ref("");
const rows = computed(() => props.canvas.offLayout.value);
const shownRows = computed(() => {
	const typed = fieldQuery.value.trim().toLowerCase();
	return rows.value.filter(({ field }) =>
		`${label(field)} ${field.fieldname}`.toLowerCase().includes(typed)
	);
});
function label(field: RawMetaField) {
	return field.label ? __(field.label, [], props.canvas.state.doctype) : field.fieldname;
}

function place(fieldname: string) {
	void acts.perform("canvas.place_field", { fieldname, ...inView() });
}

/** The end of the section in view; the open tab when it has none. */
function inView() {
	const section = props.canvas.targetSection();
	return section ? props.canvas.addPlace(section) : { tab: props.canvas.openTab.value?.name };
}
</script>
