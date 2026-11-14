<!-- The field's Rules: Visible if, Mandatory if and Read-only if, each one line in words. -->
<template>
	<PanelSection :label="__('Rules')" :count="rows.filter((row) => row.value).length">
		<RuleRow
			v-for="row in rows"
			:key="row.rule.key"
			:label="__(row.rule.label)"
			:value="row.value"
			:summary="words.say(row.value, __(row.rule.empty))"
			:sentence="words.sentence(row.rule, row.value)"
			:subject="field.label || field.fieldname"
			:note="__(row.rule.note)"
			:row-key="`${field.fieldname}.${row.rule.key}`"
			:codec="words"
			:fields="words.scope.fields"
			:referable="words.referable()"
			:commit="row.commit"
			v-bind="panelMark(canvas, field.fieldname, row.rule.key)"
		/>
	</PanelSection>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { panelMark } from "./fieldPanel";
import PanelSection from "./PanelSection.vue";
import { FIELD_RULES, ruleValue } from "./ruleRows";
import RuleRow from "./RuleRow.vue";
import { RuleWords } from "./ruleWords";

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();

const words = computed(() => RuleWords.of(props.canvas));
// Each commit names the field it was drawn for: a dialog closing as another field is picked stages here.
const rows = computed(() => {
	const { fieldname } = props.field;
	return FIELD_RULES.map((rule) => ({
		rule,
		value: ruleValue(props.field, rule),
		commit: (value: string) =>
			void acts.perform("fields.set_field_property", {
				fieldname,
				property: rule.key,
				value,
			}),
	}));
});
</script>
