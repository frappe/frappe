<template>
	<div class="column flex flex-col gap-4 min-w-0 flex-1">
		<div v-if="column.label && !column.hideLabel" class="text-ink-gray-9 max-w-fit text-base">
			{{ column.label }}
		</div>
		<template v-for="entry in entries" :key="entry.key">
			<FormLayoutPart v-if="entry.part" :part="entry.part" />
			<FormLayoutField v-else-if="entry.field" :field="entry.field" />
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import FormLayoutField from "./FormLayoutField.vue";
import FormLayoutPart from "./FormLayoutPart.vue";
import type { Column, ColumnPart, FieldNode } from "./types";

const props = defineProps<{ column: Column }>();

type Entry = { key: string; name: string; field?: FieldNode; part?: ColumnPart };

// A part keeps its place beside a hidden field, so the fields are filtered last.
const entries = computed<Entry[]>(() => {
	const rows: Entry[] = props.column.fields.map((field) => ({
		key: `field:${field.fieldname}`,
		name: field.fieldname,
		field,
	}));
	let pending = props.column.parts ?? [];
	while (pending.length) {
		const left = pending.filter((part) => !placeAt(rows, part));
		if (left.length === pending.length) break;
		pending = left;
	}
	for (const part of pending) rows.push(partEntry(part));
	return rows.filter((entry) => !entry.field?.hidden);
});

function placeAt(rows: Entry[], part: ColumnPart) {
	const anchor = rows.findIndex((entry) => entry.name === (part.before ?? part.after));
	if (anchor === -1) return false;
	rows.splice(part.before ? anchor : anchor + 1, 0, partEntry(part));
	return true;
}

function partEntry(part: ColumnPart): Entry {
	return { key: `part:${part.name}`, name: part.name, part };
}
</script>
