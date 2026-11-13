<!-- "By pattern": the pattern in a draft that commits on blur or Enter, chips that insert a token
     at the caret, and the next name it gives. A dotted pattern ("ST-.#####") stays dotted. -->
<template>
	<TextInput
		ref="input"
		v-model="draft"
		class="w-[280px] [&_input]:font-mono"
		:placeholder="dotted ? 'ST-.YYYY.-.#####' : 'ST-{YYYY}-{#####}'"
		data-naming-pattern
		@blur="commit"
		@keydown.enter.prevent="commit"
		@update:model-value="refusal = ''"
	/>
	<p v-if="refusal" class="text-p-sm text-ink-red-5" data-pattern-refusal>{{ refusal }}</p>
	<div v-if="!dotted" class="flex flex-wrap items-center gap-1.5">
		<Button
			v-for="token in tokens"
			:key="token"
			size="sm"
			variant="subtle"
			class="font-mono"
			:label="token"
			@mousedown.prevent
			@click="insert(token)"
		/>
	</div>
	<p class="text-p-sm text-ink-gray-5">
		{{ __("Next name:") }}
		<NamePreview v-if="draft.trim()" :parts="nextName(full, counters, view.label.bind(view), new Date())" />
		<span v-else class="text-ink-gray-4">{{ __("Type a pattern") }}</span>
	</p>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, ref, watch } from "vue";
import { Button, TextInput } from "frappe-ui";
import { __ } from "@/i18n";
import NamePreview from "./NamePreview.vue";
import { TOKENS, insertToken, nextName } from "./namingPattern";
import { patternRefusal } from "./namingRules";
import { SettingsViewKey } from "./settingsView";

const props = defineProps<{ autoname: string; counters: Record<string, number> }>();
const view = inject(SettingsViewKey)!;

const FORMAT = "format:";
const dotted = computed(() => !props.autoname.toLowerCase().startsWith(FORMAT));
const body = () => (dotted.value ? props.autoname : props.autoname.slice(FORMAT.length));
const draft = ref(body());
const refusal = ref("");
watch(() => props.autoname, () => (draft.value = body()));

const full = computed(() => (dotted.value ? draft.value : FORMAT + draft.value));
const tokens = computed(() => {
	const field = view.fields.find((one) => one.fieldname && ["Data", "Link", "Select"].includes(one.fieldtype));
	return field ? [...TOKENS, `{${field.fieldname}}`] : TOKENS;
});

const input = ref<{ inputElement: HTMLInputElement | null } | null>(null);

function commit() {
	const pattern = full.value.trim();
	if (!draft.value.trim() || pattern === props.autoname) return;
	refusal.value = patternRefusal(pattern);
	if (!refusal.value) view.setNaming(pattern);
}

async function insert(token: string) {
	const element = input.value?.inputElement;
	const caret = element?.selectionStart ?? draft.value.length;
	const next = insertToken(draft.value, token, caret);
	draft.value = next.pattern;
	await nextTick();
	element?.focus();
	element?.setSelectionRange(next.caret, next.caret);
}
</script>
