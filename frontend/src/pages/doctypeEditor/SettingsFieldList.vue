<!-- A list of fields as chips, with a picker to add one: the "Search by" row. The property holds
     the fieldnames comma-separated. -->
<template>
	<div class="flex flex-wrap items-center gap-1.5" data-setting-fields>
		<span
			v-for="fieldname in picked"
			:key="fieldname"
			class="inline-flex h-7 items-center gap-1 rounded-4 bg-surface-gray-2 pl-2.5 pr-1 text-base text-ink-gray-8"
		>
			{{ view.label(fieldname) }}
			<button
				type="button"
				class="grid size-5 place-items-center rounded-3 text-ink-gray-5 hover:bg-surface-gray-4 hover:text-ink-gray-8"
				:aria-label="__('Remove {0}', [view.label(fieldname)])"
				@click="save(picked.filter((other) => other !== fieldname))"
			>
				<span class="lucide-x size-3.5" aria-hidden="true" />
			</button>
		</span>
		<Combobox
			:key="picked.join()"
			class="w-40"
			variant="subtle"
			:model-value="''"
			:options="options"
			:placeholder="__('Add a field')"
			@update:model-value="$event && save([...picked, String($event)])"
		>
			<template #prefix><span class="lucide-plus size-4 text-ink-gray-5" aria-hidden="true" /></template>
		</Combobox>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Combobox } from "frappe-ui";
import { __ } from "@/i18n";
import type { SettingRow } from "./settingsRows";
import { SettingsViewKey } from "./settingsView";

const props = defineProps<{ row: SettingRow }>();
const view = inject(SettingsViewKey)!;
const prop = props.row.props[0];

const picked = computed(() =>
	String(view.value(prop) || "")
		.split(",")
		.map((fieldname) => fieldname.trim())
		.filter(Boolean),
);
const options = computed(() =>
	view.fieldOptions(props.row.fieldtypes ?? []).filter((option) => !picked.value.includes(option.value)),
);

const save = (fieldnames: string[]) => view.set({ [prop]: fieldnames.join(",") });
</script>
