<script setup>
import { computed, provide } from "vue";
import { List, ListCell, ListRow } from "frappe-ui/list";
import { CommitKey, NO_COMMIT, getFieldComponent, resolveLayout } from "@framework/ui/FormLayout";
import { DocKey, ResolveFieldKey, UpdateKey } from "@framework/ui/components/FormLayout/types";
import FormLayoutField from "@framework/ui/components/FormLayout/FormLayoutField.vue";
import ChildRows from "./ChildRows.vue";

// A layout drawn as a property list: each field a row with its label beside its control. A child
// table, code, long text or a section's part takes the row's whole width, under its label.
const props = defineProps({
	layout: { type: Array, required: true },
	doc: { type: Object, required: true },
});

const WIDE = new Set([
	"Table",
	"Table MultiSelect",
	"Code",
	"JSON",
	"HTML",
	"HTML Editor",
	"Text Editor",
	"Markdown Editor",
	"Text",
	"Small Text",
	"Long Text",
]);

provide(
	DocKey,
	computed(() => props.doc)
);
provide(UpdateKey, (fieldname, value) => (props.doc[fieldname] = value));
provide(ResolveFieldKey, getFieldComponent);
provide(CommitKey, NO_COMMIT);

const rows = computed(() => {
	const rows = [];
	for (const section of resolveLayout(props.layout, props.doc).flatMap((tab) => tab.sections)) {
		if (section.hidden) continue;
		if (section.part) {
			rows.push({
				key: section.part.name,
				label: section.label,
				part: section.part,
				wide: true,
			});
			continue;
		}
		for (const field of section.columns.flatMap((column) => column.fields)) {
			if (field.hidden) continue;
			rows.push({
				key: field.fieldname,
				label: field.label,
				reqd: field.reqd,
				wide: WIDE.has(field.fieldtype),
				field: { ...field, label: undefined, description: undefined },
			});
		}
	}
	return rows;
});
</script>

<template>
	<List :columns="['7.5rem', 'minmax(0,1fr)']" divider="none" class="list-gap-3">
		<ListRow v-for="row in rows" :key="row.key" class="py-1">
			<ListCell v-if="row.wide" class="col-span-2">
				<div class="flex w-full min-w-0 flex-col gap-1.5">
					<span v-if="row.label" class="text-sm text-ink-gray-6">
						{{ row.label }}
						<span v-if="row.reqd" class="text-ink-red-5">*</span>
					</span>
					<component :is="row.part.component" v-if="row.part" v-bind="row.part.props" />
					<ChildRows
						v-else-if="row.field.fieldtype === 'Table'"
						:field="row.field"
						:doc="doc"
					/>
					<FormLayoutField v-else :field="row.field" />
				</div>
			</ListCell>
			<template v-else>
				<ListCell>
					<span class="truncate text-sm text-ink-gray-6" :title="row.label">
						{{ row.label }}
						<span v-if="row.reqd" class="text-ink-red-5">*</span>
					</span>
				</ListCell>
				<ListCell class="[&_[data-slot=trigger]]:w-full">
					<FormLayoutField class="w-full min-w-0" :field="row.field" />
				</ListCell>
			</template>
		</ListRow>
	</List>
</template>
