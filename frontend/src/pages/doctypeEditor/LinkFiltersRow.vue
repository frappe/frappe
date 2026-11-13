<!-- A Link field's Filters (`link_filters`): which records its picker offers. The rule popover's
     builder against the target DocType's fields, read through the meta cache; a flat AND list. -->
<template>
	<RuleRow
		:label="__('Filters')"
		:value="value"
		:summary="summary"
		:sentence="filters.sentence(value)"
		:subject="field.label || field.fieldname"
		:note="__('Every {0} is offered. Add a filter to offer fewer.', [__(doctype)])"
		:row-key="`${field.fieldname}.link_filters`"
		:codec="filters"
		:fields="filters.fields"
		:referable="words.referable()"
		:commit="commit"
		:disabled="!meta && !(error && value)"
		filters
	>
		<p
			v-if="refusal"
			class="px-2 pb-1 pt-0.5 text-p-sm text-ink-gray-5"
			data-link-filters-note
		>
			{{ refusal }}
		</p>
	</RuleRow>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { isApiError } from "@framework/ui/api";
import { getFilterableFields } from "@framework/ui/Filter";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { LinkFilters } from "./linkFilters";
import RuleRow from "./RuleRow.vue";
import { RuleWords } from "./ruleWords";

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();

const doctype = computed(() => props.field.options ?? "");
const value = computed(() => String(props.field.link_filters ?? ""));
const { meta, error } = useDoctypeMeta(doctype);

const words = computed(() => RuleWords.of(props.canvas));
const filters = computed(() => {
	const fields = meta.value?.fields ? getFilterableFields(meta.value.fields, doctype.value) : [];
	return new LinkFilters(doctype.value, fields, words.value);
});
const summary = computed(() =>
	meta.value || value.value
		? filters.value.say(value.value)
		: { kind: "empty" as const, text: error.value ? __("None") : __("Loading…") }
);
const refusal = computed(() => {
	if (!error.value) return "";
	if (value.value)
		return __("{0} could not be read, so its filters show as code.", [__(doctype.value)]);
	return isApiError(error.value) && error.value.status === 403
		? __("You cannot read {0}, so its filters cannot be edited here.", [__(doctype.value)])
		: __("{0} could not be loaded, so its filters cannot be edited here.", [
				__(doctype.value),
		  ]);
});

// The commit names the field it was drawn for, as the rule rows do.
const commit = computed(() => {
	const { fieldname } = props.field;
	return (next: string) =>
		void acts.perform("fields.set_field_property", {
			fieldname,
			property: "link_filters",
			value: next,
		});
});
</script>
