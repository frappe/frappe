<!-- One Danger zone row: what the act does to this DocType, and a red button that runs it. The act
     asks with its own dialog and writes at once, outside Save and undo. -->
<template>
	<SettingsRow
		:row="row"
		compact
		class="!py-3 [&:not(:first-child)]:border-t border-outline-gray-1"
	>
		<template #help>{{ help }}</template>
		<Button
			variant="subtle"
			theme="red"
			:label="__(row.button!)"
			:data-danger="row.key"
			@click="acts.perform(`danger.${row.key}`)"
		/>
	</SettingsRow>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Button } from "frappe-ui";
import { acts } from "@/acts/dispatcher";
import { __, __n } from "@/i18n";
import SettingsRow from "./SettingsRow.vue";
import { KINDS, type SettingRow } from "./settingsRows";
import { SettingsViewKey } from "./settingsView";

const props = defineProps<{ row: SettingRow }>();
const view = inject(SettingsViewKey)!;

const help = computed(() => {
	const { doctype, settings } = view;
	if (props.row.key === "change_kind") {
		const kind = KINDS.find((one) => one.value === view.kind)!;
		return __("{0} is a {1} DocType. Changing it adds or removes fields and rights.", [
			doctype,
			__(kind.label),
		]);
	}
	if (props.row.key === "rename_doctype" && !Number(settings.properties.custom))
		return __(
			"Renames its table, every field that points to it, its folder and its controller."
		);
	if (props.row.key === "move_doctype") return __("In the {0} module.", [view.module]);
	if (props.row.key === "delete_doctype" && settings.records === 0)
		return __("Deletes {0} and all its records, none of which you can read.", [doctype]);
	if (props.row.key === "delete_doctype" && settings.records !== null)
		return __n(
			"Deletes {0} and its {1} record.",
			"Deletes {0} and its {1} records.",
			settings.records,
			[doctype, settings.records.toLocaleString()]
		);
	return __(props.row.help);
});
</script>
