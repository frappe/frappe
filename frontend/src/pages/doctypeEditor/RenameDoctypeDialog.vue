<!-- The Danger zone's Rename: the new name, and what moves with it. It closes with the name. -->
<template>
	<form class="flex flex-col gap-4" data-rename-doctype-dialog @submit.prevent="rename">
		<TextInput ref="input" v-model="name" :label="__('New name')" />
		<ul class="flex flex-col gap-1.5 text-p-base text-ink-gray-7">
			<li class="flex items-start gap-2">
				<span
					class="lucide-arrow-right mt-0.5 size-4 shrink-0 text-ink-gray-5"
					aria-hidden="true"
				/>
				<span>
					<template v-for="(part, i) in tableLine" :key="i"
						><code v-if="part.table" class="font-mono text-sm">{{ part.table }}</code
						><template v-else>{{ part.text }}</template></template
					>
				</span>
			</li>
			<li v-if="linkFields !== null" class="flex items-start gap-2" data-rename-links>
				<span
					class="lucide-arrow-right mt-0.5 size-4 shrink-0 text-ink-gray-5"
					aria-hidden="true"
				/>
				<span>{{ linkLine }}</span>
			</li>
		</ul>
		<div class="flex justify-end gap-2">
			<Button :label="__('Cancel')" @click="close(null)" />
			<Button type="submit" variant="solid" :label="__('Rename')" :disabled="!changed" />
		</div>
	</form>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Button, TextInput, type TextInputExposed } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import { __, __n } from "@/i18n";

const EFFECTS = "frappe.desk.doctype_editor.danger.rename_effects";
const props = defineProps<{
	doctype: string;
	records: number | null;
	close: (name: string | null) => void;
}>();

const name = ref(props.doctype);
const input = ref<TextInputExposed | null>(null);
// The dialog loads after it opens, too late for its own autofocus.
onMounted(() => {
	input.value?.focus();
	runMethod<number>(EFFECTS, { doctype: props.doctype }, { http: "GET" })
		.then(({ data }) => (linkFields.value = data))
		.catch(() => {});
});
// `null` until the server counts them; a failed count leaves the line out.
const linkFields = ref<number | null>(null);
const target = computed(() => name.value.trim() || props.doctype);
// The sentence is translated with {0} and {1} left in it, then split there, so the two table names
// can be set in the code font.
const tableLine = computed(() => {
	const tables = [`tab${props.doctype}`, `tab${target.value}`];
	const marks = ["{0}", "{1}"];
	const sentence =
		props.records === null
			? __("The table {0} becomes {1}.", marks)
			: __n(
					"The table {0} becomes {1}, with its {2} record.",
					"The table {0} becomes {1}, with its {2} records.",
					props.records,
					[...marks, props.records.toLocaleString()]
			  );
	return sentence
		.split(/(\{[01]\})/)
		.map((text) => (/^\{[01]\}$/.test(text) ? { table: tables[Number(text[1])] } : { text }));
});
const linkLine = computed(() =>
	__n(
		"{0} Link and Table field in other DocTypes points to {1}.",
		"{0} Link and Table fields in other DocTypes point to {1}.",
		linkFields.value ?? 0,
		[String(linkFields.value), target.value]
	)
);
const changed = computed(() => target.value !== props.doctype);

function rename() {
	if (changed.value) props.close(target.value);
}
</script>
