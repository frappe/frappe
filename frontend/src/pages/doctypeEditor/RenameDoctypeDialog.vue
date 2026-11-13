<!-- The Danger zone's Rename: the new name, and what moves with it. It closes with the name. -->
<template>
	<form class="flex flex-col gap-4" data-rename-doctype-dialog @submit.prevent="rename">
		<TextInput ref="input" v-model="name" :label="__('New name')" />
		<p class="text-p-base text-ink-gray-7">
			{{
				__(
					"Its table {0} becomes {1}, and every Link and Table field that points to it follows.",
					[`tab${doctype}`, `tab${target}`]
				)
			}}
		</p>
		<div class="flex justify-end gap-2">
			<Button :label="__('Cancel')" @click="close(null)" />
			<Button type="submit" variant="solid" :label="__('Rename')" :disabled="!changed" />
		</div>
	</form>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Button, TextInput, type TextInputExposed } from "frappe-ui";
import { __ } from "@/i18n";

const props = defineProps<{ doctype: string; close: (name: string | null) => void }>();

const name = ref(props.doctype);
const input = ref<TextInputExposed | null>(null);
// The dialog loads after it opens, too late for its own autofocus.
onMounted(() => input.value?.focus());
const target = computed(() => name.value.trim() || props.doctype);
const changed = computed(() => target.value !== props.doctype);

function rename() {
	if (changed.value) props.close(target.value);
}
</script>
