<!-- "Add a layout": its title, type, the condition it shows under, started from a copy of the
     type's default or empty. It closes with the layout to add once the save would take it. -->
<template>
	<form class="flex flex-col gap-5" data-add-layout-dialog @submit.prevent="add">
		<FormControl
			v-model="layout.title"
			:label="__('Title')"
			:placeholder="__('Passive contacts')"
			required
			autocomplete="off"
			autofocus
			data-add-layout-title
		/>
		<FormControl
			v-model="layout.type"
			type="select"
			:label="__('Based on')"
			:options="types"
		/>
		<FormControl
			v-model="layout.condition"
			:label="__('Show it when')"
			:placeholder="`doc.status == 'Passive'`"
			:description="
				__(
					'A JavaScript expression on doc. The first layout whose condition matches wins; otherwise the default one shows.'
				)
			"
			required
			autocomplete="off"
			class="[&_input]:font-mono"
			data-add-layout-condition
		/>
		<div class="flex flex-col gap-1.5">
			<FormLabel :label="__('Start from')" />
			<TabButtons
				v-model="layout.start"
				:options="starts"
				class="[&>*]:w-full [&_button]:flex-1 [&_button]:justify-center"
			/>
		</div>
		<ErrorMessage v-if="shownRefusal" :message="shownRefusal" data-add-layout-refusal />
		<div class="flex justify-end gap-2">
			<Button :label="__('Cancel')" @click="close(null)" />
			<Button
				type="submit"
				variant="solid"
				:label="__('Create')"
				:disabled="!ready"
				data-add-layout-submit
			/>
		</div>
	</form>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { Button, ErrorMessage, FormControl, FormLabel, TabButtons } from "frappe-ui";
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
	{ value: "copy", label: __("A copy of {0}", [label.value]) },
	{ value: "empty", label: __("Empty") },
]);
const refusal = computed(() =>
	addLayoutRefusal(props.working, {
		type: layout.type,
		title: layout.title.trim(),
		condition: layout.condition.trim(),
	})
);
const ready = computed(() => Boolean(layout.title.trim() && layout.condition.trim()));
const shownRefusal = computed(() => (tried.value ? refusal.value : null));

function add() {
	tried.value = true;
	if (!ready.value || refusal.value) return;
	props.close({ ...layout, title: layout.title.trim(), condition: layout.condition.trim() });
}
</script>
