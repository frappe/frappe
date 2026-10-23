<template>
	<SettingsPage :title="title" :description="description" :back="back" @back="emit('close')">
		<slot />
		<form v-if="doc" ref="form" class="mt-2 flex flex-col gap-4" @submit.prevent="save">
			<div
				v-if="doc.is_system_generated"
				class="rounded-6 border border-outline-gray-2 bg-surface-gray-1 px-3 py-2 text-xs text-ink-gray-7"
			>
				Comes with an app, so greyed-out fields can't be changed.
			</div>
			<FieldControl
				v-for="field in visibleFields"
				:key="field.name"
				:field="field"
				:doc="doc"
				:disabled="!canWrite || isLocked(field)"
			/>
		</form>
		<div v-else-if="error" class="py-8 text-center text-xs text-ink-gray-5">
			{{ error }}
		</div>
		<LoadingState v-else class="justify-center py-8 text-xs text-ink-gray-5" />
		<template v-if="doc" #footer>
			<Button
				v-for="action in actions"
				:key="action.label"
				variant="outline"
				:label="action.label"
				:loading="running === action.label"
				:disabled="dirty"
				:title="dirty ? 'Save first' : ''"
				@click="runAction(action)"
			/>
			<span class="min-w-0 flex-1"><ErrorMessage :message="error" /></span>
			<Button v-if="canDelete" variant="ghost" theme="red" label="Delete" @click="remove" />
			<!-- a narrow frame's header leads back to the list instead -->
			<Button
				v-if="!spec.single"
				variant="outline"
				label="Cancel"
				class="max-md:hidden"
				@click="emit('close')"
			/>
			<Button
				v-if="canWrite"
				variant="solid"
				:label="isNew ? 'Create' : 'Save'"
				:loading="saving"
				:disabled="!dirty"
				@click="save"
			/>
		</template>
	</SettingsPage>
</template>

<script setup>
import { Button, ErrorMessage } from "frappe-ui";
import LoadingState from "@flow/ui-core/components/LoadingState.vue";
import SettingsPage from "@flow/ui-core/components/SettingsPage.vue";

import FieldControl from "./FieldControl.vue";
import { useRecord } from "./records.js";

// One document of the spec's doctype, as a settings page (see useRecord). The default slot
// renders above the fields, for a page's own tabs.
const props = defineProps({
	spec: { type: Object, required: true },
	name: { type: String, default: null },
	title: { type: String, required: true },
	description: { type: String, default: "" },
	back: { type: String, default: "" }, // the way back to a list, when there is one
});
const emit = defineEmits(["saved", "deleted", "close"]);
const {
	doc,
	form,
	error,
	saving,
	running,
	isNew,
	canWrite,
	canDelete,
	dirty,
	visibleFields,
	actions,
	isLocked,
	save,
	remove,
	runAction,
} = useRecord(props, emit);
</script>
