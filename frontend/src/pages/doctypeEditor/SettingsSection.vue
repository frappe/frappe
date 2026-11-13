<!-- One Settings section's rows, in their groups. Naming's rule and the permissions table are
     their own components; every other row is a SettingsRow with its control. -->
<template>
	<div class="flex flex-col" :data-section="section">
		<template v-for="group in groups" :key="group.label">
			<component
				:is="group.label ? SettingsGroup : 'div'"
				v-bind="group.label ? { label: __(group.label) } : {}"
			>
				<template v-for="row in group.rows" :key="row.key">
					<SettingsNaming v-if="row.control === 'naming'" :row="row" />
					<SettingsPermissions v-else-if="row.control === 'permissions'" :row="row" />
					<SettingsRow v-else :row="row" :wide="WIDE.includes(row.control)">
						<SettingsControl :row="row" />
					</SettingsRow>
				</template>
			</component>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { __ } from "@/i18n";
import SettingsControl from "./SettingsControl.vue";
import SettingsGroup from "./SettingsGroup.vue";
import SettingsNaming from "./SettingsNaming.vue";
import SettingsPermissions from "./SettingsPermissions.vue";
import SettingsRow from "./SettingsRow.vue";
import {
	settingRows,
	type RowControl,
	type SettingRow,
	type SettingsSection,
} from "./settingsRows";
import { SettingsViewKey } from "./settingsView";

const props = defineProps<{ section: SettingsSection }>();
const view = inject(SettingsViewKey)!;

const WIDE: RowControl[] = ["fields", "kind"];

/** The section's rows under their headings, in catalogue order. */
const groups = computed(() => {
	const groups: { label: string; rows: SettingRow[] }[] = [];
	for (const row of settingRows(view.settings).filter((one) => one.section === props.section)) {
		const last = groups.at(-1);
		if (last?.label === row.group) last.rows.push(row);
		else groups.push({ label: row.group, rows: [row] });
	}
	return groups;
});
</script>
