<!-- "Add field" in a section: the label is typed in place, beside the type its words suggest. Enter
     adds the field and keeps the row open for the next one; Escape closes it. -->
<template>
	<div v-if="open" class="flex items-center gap-2" data-canvas-add-row>
		<TextInput
			ref="input"
			v-model="label"
			class="min-w-0 flex-1"
			:placeholder="__('Field label')"
			@keydown.enter.prevent="add"
			@keydown.esc.prevent="close"
			@blur="!label.trim() && close()"
		/>
		<Badge
			theme="gray"
			size="lg"
			:label="typeLabel"
			:title="guess.because ? __('Because the label says {0}', [guess.because]) : undefined"
			data-canvas-guessed-type
		/>
	</div>
	<div v-else class="flex w-fit" data-canvas-add-field>
		<Button
			variant="subtle"
			size="sm"
			icon-left="lucide-plus"
			:label="__('Add field')"
			@click.stop="canvas.adding.value = section"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { Badge, Button, TextInput } from "frappe-ui";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { guessFieldtype } from "./fieldRules";

const props = defineProps<{ canvas: DesignCanvas; section: string }>();

const input = ref<{ focus: () => void } | null>(null);
const label = ref("");
const open = computed(() => props.canvas.adding.value === props.section);
const guess = computed(() => guessFieldtype(label.value));
const typeLabel = computed(() => {
	const fieldtype = __(guess.value.fieldtype);
	return guess.value.options ? `${fieldtype} · ${__(guess.value.options)}` : fieldtype;
});

watch(
	open,
	async (opened) => {
		if (!opened) return;
		label.value = "";
		await nextTick();
		input.value?.focus();
	},
	{ immediate: true }
);

async function add() {
	const typed = label.value.trim();
	if (!typed) return;
	const { fieldtype, options } = guess.value;
	const count = props.canvas.working.value.fields.length;
	await acts.perform("fields.add_field", {
		label: typed,
		fieldtype,
		...(options ? { options } : {}),
		...props.canvas.addPlace(props.section),
	});
	if (props.canvas.working.value.fields.length > count) label.value = "";
}

function close() {
	if (open.value) props.canvas.adding.value = null;
}
</script>
