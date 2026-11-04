<!-- The Cards type's control among the page's: which fields a card's title and body read. -->
<template>
	<Popover side="bottom" align="end">
		<template #trigger>
			<Button :label="__('Cards')" icon-left="lucide-layout-grid" />
		</template>
		<template #default>
			<div class="flex min-w-60 flex-col gap-3 p-3">
				<FormControl
					type="select"
					:label="__('Title')"
					:modelValue="title"
					:options="titleOptions"
					@update:modelValue="update({ title_field: $event })"
				/>
				<FormControl
					type="select"
					:label="__('Body')"
					:modelValue="body ?? ''"
					:options="bodyOptions"
					@update:modelValue="update({ body_field: $event })"
				/>
			</div>
		</template>
	</Popover>
</template>

<script setup lang="ts">
import { NO_VALUE } from "@framework/ui/FormLayout/noValueFields";
import { Button, FormControl, Popover } from "frappe-ui";
import { computed } from "vue";
import { __ } from "@/i18n";
import type { ListMeta } from "@/list/defaults";
import { BODY_FIELDTYPES } from "./cardFields";

const props = defineProps<{
	meta: ListMeta | null;
	title: string;
	body: string | null;
	update: (patch: Record<string, unknown>) => void;
}>();

const shown = computed(() =>
	(props.meta?.fields ?? []).filter((field) => !NO_VALUE.has(field.fieldtype) && !field.hidden)
);
const option = (field: { fieldname: string; label?: string }) => ({
	label: field.label || field.fieldname,
	value: field.fieldname,
});

const titleOptions = computed(() => [
	{ label: __("ID"), value: "name" },
	...shown.value.map(option),
]);
const bodyOptions = computed(() => [
	{ label: __("None"), value: "" },
	...shown.value.filter((field) => BODY_FIELDTYPES.has(field.fieldtype)).map(option),
]);
</script>
