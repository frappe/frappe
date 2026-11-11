<script setup>
import { computed } from "vue";
import { Button } from "frappe-ui";
import { List, ListCell, ListHeader, ListHeaderCell, ListRow } from "frappe-ui/list";
import { getFieldComponent, newRowValues } from "@framework/ui/FormLayout";

// A child table as a plain list: a column per grid field, a remove button per row and one to add.
const props = defineProps({
	field: { type: Object, required: true },
	doc: { type: Object, required: true },
});

const __ = window.__;
const columns = computed(() => props.field.childFields || []);
const rows = computed(() => props.doc[props.field.fieldname] || []);
const tracks = computed(() => [
	...columns.value.map((df) => (df.fieldtype === "Check" ? "4.5rem" : "minmax(0,1fr)")),
	"1.75rem",
]);

function add() {
	const list = (props.doc[props.field.fieldname] ||= []);
	list.push({ ...newRowValues(columns.value), idx: list.length + 1 });
}

function remove(index) {
	const list = props.doc[props.field.fieldname];
	list.splice(index, 1);
	list.forEach((row, i) => (row.idx = i + 1));
}
</script>

<template>
	<div class="flex flex-col gap-1.5">
		<List v-if="rows.length" :columns="tracks" divider="none" class="list-gap-2">
			<ListHeader>
				<ListHeaderCell v-for="df in columns" :key="df.fieldname">
					<span class="text-xs text-ink-gray-5">{{ df.label }}</span>
				</ListHeaderCell>
				<ListHeaderCell />
			</ListHeader>
			<ListRow v-for="(row, index) in rows" :key="row.name || index" class="group py-0.5">
				<ListCell
					v-for="df in columns"
					:key="df.fieldname"
					class="[&_[data-slot=trigger]]:w-full [&>*]:w-full"
				>
					<component
						:is="getFieldComponent(df.fieldtype)"
						v-bind="df.ui?.props"
						:field="{
							...df,
							label: undefined,
							readOnly: df.readOnly || field.readOnly,
						}"
						:model-value="row[df.fieldname]"
						@update:model-value="(value) => (row[df.fieldname] = value)"
						v-on="df.ui?.on ?? {}"
					/>
				</ListCell>
				<ListCell>
					<Button
						v-if="!field.readOnly"
						class="opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
						size="sm"
						variant="ghost"
						icon="lucide-x"
						:label="__('Remove row')"
						@click="remove(index)"
					/>
				</ListCell>
			</ListRow>
		</List>
		<Button
			v-if="!field.readOnly"
			class="self-start"
			size="sm"
			icon-left="lucide-plus"
			:label="__('Add row')"
			@click="add"
		/>
	</div>
</template>
