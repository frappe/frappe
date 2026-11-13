<!-- The Naming Series list: the options of the naming_series field, each with the next name it
     gives. One is the default; a series can be added, removed or made the default. -->
<template>
	<div class="flex w-full flex-col" data-naming-series>
		<div v-for="option in options" :key="option" class="group/series flex h-8 items-center gap-3" :data-series="option">
			<span class="flex w-[296px] shrink-0 items-center gap-2">
				<span class="min-w-0 truncate font-mono text-sm text-ink-gray-8">{{ option }}</span>
				<Badge v-if="option === preferred" :label="__('Default')" theme="gray" size="sm" class="shrink-0" />
			</span>
			<NamePreview class="min-w-0 flex-1 truncate" :parts="nextName(option, counters, view.label.bind(view), new Date())" />
			<span class="flex shrink-0 items-center gap-1 opacity-0 group-hover/series:opacity-100 focus-within:opacity-100">
				<Button v-if="option !== preferred" size="sm" variant="ghost" :label="__('Make default')" @click="save(options, option)" />
				<Button
					v-if="options.length > 1"
					size="sm"
					variant="ghost"
					icon="lucide-x"
					:aria-label="__('Remove {0}', [option])"
					@click="remove(option)"
				/>
			</span>
		</div>
		<TextInput
			v-model="adding"
			class="mt-1 w-[280px] [&_input]:font-mono"
			:placeholder="__('Add a series, like {0}', [example])"
			data-series-add
			@keydown.enter.prevent="add"
			@blur="add"
		/>
		<p class="mt-1.5 text-p-sm text-ink-gray-5">
			{{ __("A dot ends the text part; # marks the counter's digits.") }}
		</p>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, ref } from "vue";
import { Badge, Button, TextInput } from "frappe-ui";
import { __ } from "@/i18n";
import NamePreview from "./NamePreview.vue";
import { nextName } from "./namingPattern";
import { SettingsViewKey } from "./settingsView";

defineProps<{ counters: Record<string, number> }>();
const view = inject(SettingsViewKey)!;

const field = computed(() => view.fields.find((one) => one.fieldname === "naming_series"));
const options = computed(() =>
	String(field.value?.options ?? "")
		.split("\n")
		.map((option) => option.trim())
		.filter(Boolean),
);
const preferred = computed(() => String(field.value?.default || options.value[0] || ""));
const example = computed(() => options.value[0] || "ST-.YYYY.-.#####");
const adding = ref("");

function add() {
	const option = adding.value.trim();
	if (!option || options.value.includes(option)) return;
	adding.value = "";
	save([...options.value, option], preferred.value || option);
}

function remove(option: string) {
	const rest = options.value.filter((one) => one !== option);
	save(rest, option === preferred.value ? rest[0] : preferred.value);
}

const save = (list: string[], chosen: string) => view.setSeries(list, chosen);
</script>
