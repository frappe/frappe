<!-- The panel outside Details with nothing selected: the fields this layout does not place, then
     the field types as "New field". A click places the field, or adds one of the type, at the end
     of the section in view; a field made here goes on this layout only. -->
<template>
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
	<div class="flex flex-col" data-panel-new-field>
		<PanelSection :label="__('New field')">
			<TextInput v-model="typeQuery" :placeholder="__('Find a field type')">
				<template #prefix
					><Icon name="lucide-search" class="size-4 text-ink-gray-5"
				/></template>
			</TextInput>
			<div v-if="types.length" class="-mx-2 flex flex-col">
				<ItemListRow
					v-for="name in types"
					:key="name"
					as="button"
					type="button"
					class="!min-h-8 text-left hover:bg-surface-gray-2"
					:data-panel-new-type="name"
					@click="add(name)"
				>
					<template #prefix
						><Icon :name="typeIcon(name)" class="size-4 text-ink-gray-5"
					/></template>
					<span class="block truncate text-ink-gray-8">{{ __(name) }}</span>
				</ItemListRow>
			</div>
			<p v-else class="text-p-sm text-ink-gray-5">{{ __("No field type matches.") }}</p>
		</PanelSection>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Badge, Icon, ItemListRow, TextInput } from "frappe-ui";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { newFieldname } from "./editorModel";
import { FIELDTYPE_GROUPS, typeIcon, typeName, typeOf } from "./fieldtypes";
import PanelSection from "./PanelSection.vue";

const props = defineProps<{ canvas: DesignCanvas }>();

const TYPES = [...FIELDTYPE_GROUPS.flatMap((group) => group.types), "Email"].sort();

const fieldQuery = ref("");
const typeQuery = ref("");
const rows = computed(() => props.canvas.offLayout.value);
const shownRows = computed(() => {
	const typed = fieldQuery.value.trim().toLowerCase();
	return rows.value.filter(({ field }) =>
		`${label(field)} ${field.fieldname}`.toLowerCase().includes(typed)
	);
});
const types = computed(() => {
	const typed = typeQuery.value.trim().toLowerCase();
	return TYPES.filter((name) => __(name).toLowerCase().includes(typed));
});

function label(field: RawMetaField) {
	return field.label ? __(field.label, [], props.canvas.state.doctype) : field.fieldname;
}

function place(fieldname: string) {
	void acts.perform("canvas.place_field", { fieldname, ...inView() });
}

function add(name: string) {
	void acts.perform("fields.add_field", {
		label: freeLabel(__(name)),
		...typeOf(name),
		...inView(),
	});
}

/** The end of the section in view; the open tab when it has none. */
function inView() {
	const section = props.canvas.targetSection();
	return section ? props.canvas.addPlace(section) : { tab: props.canvas.openTab.value?.name };
}

/** "Data", else "Data 2" and on: a label whose fieldname no field has. */
function freeLabel(base: string) {
	const { canvas } = props;
	for (let count = 1; ; count++) {
		const label = count === 1 ? base : `${base} ${count}`;
		if (!canvas.field(newFieldname(canvas.working.value, label))) return label;
	}
}
</script>
