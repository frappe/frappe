<!-- The Danger zone's Change kind: the five kinds, the current one picked, a refused one disabled with
     the reason, and what the pick changes under the list. It closes with the new kind. -->
<template>
	<div class="flex flex-col gap-4" data-change-kind-dialog>
		<RadioGroup
			padded
			class="-mx-1.5 flex flex-col gap-0.5"
			:model-value="picked"
			@update:model-value="picked = $event as DoctypeKind"
		>
			<Radio
				v-for="one in KINDS"
				:key="one.value"
				:value="one.value"
				:label="__(one.label)"
				:description="refusal(one.value) || __(one.description)"
				:disabled="Boolean(refusal(one.value))"
				:class="one.value === picked && 'bg-surface-gray-2'"
			/>
		</RadioGroup>
		<p v-if="notes.length" class="text-p-sm text-ink-gray-6" data-kind-notes>
			{{ notes.join(" ") }}
		</p>
		<div class="flex justify-end gap-2">
			<Button :label="__('Cancel')" @click="close(null)" />
			<Button
				variant="solid"
				:label="__('Change kind')"
				:disabled="picked === kind"
				@click="close(picked)"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Button, Radio, RadioGroup } from "frappe-ui";
import { __ } from "@/i18n";
import { kindNotes, kindRefusal } from "./dangerActs";
import { KINDS, type DoctypeKind } from "./settingsRows";

const props = defineProps<{
	doctype: string;
	kind: DoctypeKind;
	/** The records the reader sees; `null` when unknown. */
	records: number | null;
	close: (kind: DoctypeKind | null) => void;
}>();

const picked = ref<DoctypeKind>(props.kind);
const notes = computed(() => kindNotes(props.doctype, props.kind, picked.value));

function refusal(kind: DoctypeKind) {
	return kindRefusal(props.doctype, props.kind, kind, props.records);
}
</script>
