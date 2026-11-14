<!-- Naming: one radio row per rule; the chosen rule opens its control and its next name under it. -->
<template>
	<SettingsRow :row="row" wide>
		<RadioGroup
			:model-value="rule"
			padded
			class="-mx-1.5 flex flex-col gap-0.5"
			@update:model-value="pick($event as Rule)"
		>
			<template v-for="one in rules" :key="one.value">
				<Radio
					:value="one.value"
					:label="__(one.label)"
					:description="refusal(one.value) || __(one.help)"
					:disabled="Boolean(refusal(one.value))"
					:data-naming-rule="one.value"
				/>
				<div
					v-if="one.value === rule && CONTROLLED.includes(rule)"
					class="flex flex-col gap-2 pb-2 pl-7 pr-1.5"
					data-naming-control
				>
					<template v-if="rule === 'field'">
						<Combobox
							class="w-[280px]"
							:model-value="autoname.slice(FIELD.length)"
							:options="nameable"
							:placeholder="__('Choose a field')"
							@update:model-value="$event && view.setNaming(FIELD + $event)"
						/>
						<p class="text-p-sm text-ink-gray-5">
							{{
								__("Two records cannot share a value of {0}.", [
									view.label(autoname.slice(FIELD.length)),
								])
							}}
						</p>
					</template>
					<SettingsPattern
						v-else-if="rule === 'format'"
						:autoname="autoname"
						:counters="counters"
					/>
					<SettingsSeries v-else :counters="counters" />
				</div>
			</template>
		</RadioGroup>
	</SettingsRow>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Combobox, Radio, RadioGroup } from "frappe-ui";
import { __ } from "@/i18n";
import SettingsPattern from "./SettingsPattern.vue";
import SettingsRow from "./SettingsRow.vue";
import SettingsSeries from "./SettingsSeries.vue";
import {
	NAMEABLE_TYPES,
	RULES,
	SHOWN_WHEN_CURRENT,
	patternSeed,
	ruleOf,
	ruleRefusal,
	seriesAbbreviation,
	type Rule,
} from "./namingRules";
import { useSeriesCounters } from "./seriesCounters";
import type { SettingRow } from "./settingsRows";
import { SettingsViewKey } from "./settingsView";

defineProps<{ row: SettingRow }>();
const view = inject(SettingsViewKey)!;

const FIELD = "field:";
const CONTROLLED: Rule[] = ["field", "format", "naming_series"];

const autoname = computed(() => String(view.value("autoname") ?? ""));
const rule = computed(() => ruleOf(view.settings.properties));
const rules = computed(() =>
	RULES.filter((one) => !SHOWN_WHEN_CURRENT.includes(one.value) || one.value === rule.value)
);
const nameable = computed(() => view.fieldOptions(NAMEABLE_TYPES));
const series = computed(() => view.fields.find((field) => field.fieldname === "naming_series"));
const counters = useSeriesCounters(view, () =>
	rule.value === "format" ? [autoname.value] : String(series.value?.options ?? "").split("\n")
);

function refusal(one: Rule) {
	if (one === "field" && one !== rule.value && !nameable.value.length) {
		return __("Add a Data, Link or Select field first.");
	}
	return ruleRefusal(view.settings, view.fields, one);
}

function pick(one: Rule) {
	if (one === "field")
		return view.setNaming(
			FIELD + (String(view.value("title_field") || "") || nameable.value[0].value)
		);
	if (one === "format") return view.setNaming(patternSeed(view.doctype));
	if (one === "naming_series") {
		return view.setNaming(
			"naming_series:",
			series.value ? undefined : [`${seriesAbbreviation(view.doctype)}-.#####`]
		);
	}
	view.setNaming(one === "uuid" ? "UUID" : one);
}
</script>
