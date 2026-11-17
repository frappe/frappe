<!-- The Danger zone's Delete: what goes, and the DocType's name typed to confirm. It closes with
     `true` once the server has deleted it; a failure stays in the dialog. -->
<template>
	<form class="flex flex-col gap-4" data-delete-doctype-dialog @submit.prevent="remove">
		<p class="text-p-base text-ink-gray-7">
			{{ whatGoes }}
			{{ __("Custom fields that use it as a child table go too.") }}
		</p>
		<TextInput
			ref="input"
			v-model="typed"
			:label="__('Type {0} to confirm', [doctype])"
			:placeholder="doctype"
		/>
		<p
			class="min-h-5 text-p-sm text-ink-red-6"
			role="alert"
			:data-danger-error="error ? '' : null"
		>
			{{ error }}
		</p>
		<ConfirmNote
			kind="danger"
			:message="__('Delete {0}.', [doctype])"
			:buttons="[__('Cancel'), __('Delete {0}', [doctype])]"
		/>
		<div class="flex justify-end gap-2">
			<Button :label="__('Cancel')" :disabled="working" @click="close(null)" />
			<Button
				type="submit"
				variant="solid"
				theme="red"
				:label="__('Delete {0}', [doctype])"
				:disabled="!confirmed"
				:loading="working"
				data-danger-confirm
				:aria-busy="working"
			/>
		</div>
	</form>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Button, TextInput, type TextInputExposed } from "frappe-ui";
import { __, __n } from "@/i18n";
import ConfirmNote from "./ConfirmNote.vue";
import { useDangerSubmit } from "./dangerSubmit";

const props = defineProps<{
	doctype: string;
	/** The records the reader sees; `null` when unknown. */
	records: number | null;
	submit: () => Promise<true>;
	close: (deleted: true | null) => void;
}>();
const { working, error, send } = useDangerSubmit(props.submit, props.close);

const typed = ref("");
const input = ref<TextInputExposed | null>(null);
// The dialog loads after it opens, too late for its own autofocus.
onMounted(() => input.value?.focus());
const confirmed = computed(() => typed.value === props.doctype);
const whatGoes = computed(() => {
	const table = `tab${props.doctype}`;
	if (props.records === 0)
		return __("Deletes {0}, all its records (you can read none of them) and its table {1}.", [
			props.doctype,
			table,
		]);
	const records =
		props.records === null
			? __("its records")
			: __n("its {0} record", "its {0} records", props.records, [
					props.records.toLocaleString(),
			  ]);
	return __("Deletes {0}, {1} and its table {2}.", [props.doctype, records, table]);
});

function remove() {
	if (confirmed.value) send(undefined);
}
</script>
