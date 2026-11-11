<!-- A Check column an app's `list.js` draws as a switch: it saves the row's field in place. -->
<template>
	<div @click.stop.prevent>
		<Switch
			size="sm"
			:modelValue="checked"
			:disabled="!writable || saving"
			:aria-label="field.label"
			@update:modelValue="save"
		/>
	</div>
</template>

<script setup lang="ts">
import { updateDocument } from "@framework/ui/api";
import type { FieldMeta } from "@framework/ui/fields/types";
import { Switch, toast } from "frappe-ui";
import { computed, ref } from "vue";
import { errorMessage } from "@/recordPage";

const props = defineProps<{
	doctype: string;
	field: FieldMeta;
	row: Record<string, any>;
	writable: boolean;
}>();

const saving = ref(false);
const checked = computed(() => Boolean(props.row[props.field.fieldname]));

// The row changes only once the server accepts, so a refused write leaves the switch as it was.
async function save(on: boolean) {
	if (saving.value) return;
	saving.value = true;
	try {
		const { data } = await updateDocument(props.doctype, props.row.name, {
			[props.field.fieldname]: on ? 1 : 0,
			modified: props.row.modified,
		});
		props.row[props.field.fieldname] = data[props.field.fieldname];
		props.row.modified = data.modified;
	} catch (failure) {
		toast.error(errorMessage(failure));
	} finally {
		saving.value = false;
	}
}
</script>
