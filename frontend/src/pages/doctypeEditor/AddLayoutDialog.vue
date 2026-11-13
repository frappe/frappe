<!-- "Add a layout": its type, title and the condition it shows under, started from a copy of the
     type's default or empty. It closes with the layout to add once the save would take it. -->
<template>
	<form class="flex flex-col gap-4" data-add-layout-dialog @submit.prevent="add">
		<FormControl v-model="layout.type" type="select" :label="__('Type')" :options="types" />
		<FormControl
			v-model="layout.title"
			:label="__('Title')"
			:placeholder="__('Partner contacts')"
			autofocus
			data-add-layout-title
		/>
		<FormControl
			v-model="layout.condition"
			:label="__('Show it when')"
			:placeholder="`doc.status == 'Open'`"
			:description="
				__('JavaScript on doc, as in Depends On. Empty: the type\'s default layout.')
			"
			data-add-layout-condition
		/>
		<FormControl
			v-model="layout.start"
			type="select"
			:label="__('Start from')"
			:options="starts"
		/>
		<ErrorMessage v-if="shownRefusal" :message="shownRefusal" data-add-layout-refusal />
		<div class="flex justify-end gap-2">
			<Button :label="__('Cancel')" @click="close(null)" />
			<Button
				type="submit"
				variant="solid"
				:label="__('Add layout')"
				data-add-layout-submit
			/>
		</div>
	</form>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { Button, ErrorMessage, FormControl } from "frappe-ui";
import { __ } from "@/i18n";
import type { FormLayoutType } from "@/recordPage/formLayoutSource/types";
import type { WorkingState } from "./editorModel";
import type { AddedLayout } from "./layoutActs";
import { addLayoutRefusal } from "./layoutMenu";

const props = defineProps<{
	working: WorkingState;
	types: { value: FormLayoutType; label: string }[];
	type: FormLayoutType;
	close: (layout: AddedLayout | null) => void;
}>();

const layout = reactive<AddedLayout>({
	type: props.type,
	title: "",
	condition: "",
	start: "copy",
});
const tried = ref(false);

const label = computed(() => props.types.find((one) => one.value === layout.type)?.label ?? "");
const starts = computed(() => [
	{ value: "copy", label: __("A copy of the default {0} layout", [label.value]) },
	{ value: "empty", label: __("Empty") },
]);
const refusal = computed(() =>
	addLayoutRefusal(props.working, {
		type: layout.type,
		title: layout.title.trim(),
		condition: layout.condition.trim(),
	})
);
const shownRefusal = computed(() => (tried.value ? refusal.value : null));

function add() {
	tried.value = true;
	if (refusal.value) return;
	props.close({ ...layout, title: layout.title.trim(), condition: layout.condition.trim() });
}
</script>
