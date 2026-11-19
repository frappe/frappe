<!-- A Check column an app's `list.js` draws as a switch: it saves the row's field in place. -->
<template>
	<div class="w-fit" @click.stop.prevent>
		<Switch
			size="sm"
			:modelValue="checked"
			:disabled="!writable"
			:aria-label="`${field.label} ${row.name}`"
			@update:modelValue="save"
		/>
	</div>
</template>

<script setup lang="ts">
import { isApiError, updateDocument } from "@framework/ui/api";
import type { FieldMeta } from "@framework/ui/fields/types";
import { Switch, toast } from "frappe-ui";
import { computed, ref, watch } from "vue";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage";

const props = defineProps<{
	doctype: string;
	field: FieldMeta;
	row: Record<string, any>;
	writable: boolean;
}>();

const saving = ref(false);
// The cached row is frozen: the saved value lives here until the list reads the row again.
const saved = ref<{ value: unknown; modified: string } | null>(null);
watch(
	() => props.row.modified,
	() => (saved.value = null)
);
const checked = computed(() =>
	Boolean(saved.value ? saved.value.value : props.row[props.field.fieldname])
);

async function save(on: boolean) {
	if (saving.value) return;
	saving.value = true;
	try {
		const { data } = await updateDocument(props.doctype, props.row.name, {
			[props.field.fieldname]: on ? 1 : 0,
			modified: saved.value?.modified ?? props.row.modified,
		});
		saved.value = { value: data[props.field.fieldname], modified: data.modified };
	} catch (failure) {
		toast.error(
			isApiError(failure) && failure.isTimestampMismatch
				? __("Someone else changed this record. Reload the list and try again.")
				: errorMessage(failure)
		);
	} finally {
		saving.value = false;
	}
}
</script>
