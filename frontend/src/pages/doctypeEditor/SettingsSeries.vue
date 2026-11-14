<!-- The Naming Series list: the options of the naming_series field, each with the next name it
     gives. "Edit series" opens a dialog that edits them all at once. -->
<template>
	<div class="flex w-full flex-col" data-naming-series>
		<div
			v-for="option in options"
			:key="option"
			class="flex h-7 items-center gap-3"
			:data-series="option"
		>
			<span class="flex w-[296px] shrink-0 items-center gap-2">
				<Tooltip :text="option">
					<span class="block min-w-0 truncate font-mono text-sm text-ink-gray-8">{{ option }}</span>
				</Tooltip>
				<Badge
					v-if="option === preferred"
					:label="__('Default')"
					theme="gray"
					size="sm"
					class="shrink-0"
				/>
			</span>
			<Tooltip :text="fullName(option)">
				<NamePreview class="block min-w-0 flex-1 truncate whitespace-nowrap" :parts="next(option)" />
			</Tooltip>
		</div>
		<p class="mt-1 text-p-sm text-ink-gray-5">
			{{ __("The series are the options of the Naming Series field.") }}
		</p>
		<Button
			size="sm"
			variant="subtle"
			:label="__('Edit series')"
			class="mt-2 w-fit"
			data-series-edit
			@click="edit"
		/>
		<SeriesDialog
			v-if="shown"
			v-model:open="open"
			:series="options"
			:preferred="preferred"
			:counters="counters"
			@done="save"
			@closed="shown = false"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, ref } from "vue";
import { Badge, Button, Tooltip } from "frappe-ui";
import { __ } from "@/i18n";
import NamePreview from "./NamePreview.vue";
import SeriesDialog from "./SeriesDialog.vue";
import { nextName } from "./namingPattern";
import { SettingsViewKey } from "./settingsView";

const props = defineProps<{ counters: Record<string, number> }>();
const view = inject(SettingsViewKey)!;
// The dialog is built on open, so it starts from the field's current options each time.
const shown = ref(false);
const open = ref(false);

const field = computed(() => view.fields.find((one) => one.fieldname === "naming_series"));
const options = computed(() =>
	String(field.value?.options ?? "")
		.split("\n")
		.map((option) => option.trim())
		.filter(Boolean)
);
const preferred = computed(() => String(field.value?.default || options.value[0] || ""));

function next(option: string) {
	return nextName(option, props.counters, view.label.bind(view), new Date());
}

function fullName(option: string) {
	return next(option)
		.map((part) => part.text)
		.join("");
}

function edit() {
	shown.value = true;
	open.value = true;
}

function save(list: string[], chosen: string) {
	// The dialog puts the default first; with the same default and the same series that is no change.
	const same = [...list].sort().join("\n") === [...options.value].sort().join("\n");
	if (same && chosen === preferred.value) return;
	view.setSeries(list, chosen);
}
</script>
