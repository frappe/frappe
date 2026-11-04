<template>
	<PageHeader :icon="info.icon" :title="name ?? `New ${spec.singular}`">
		<template #actions>
			<span v-if="doc && !canWrite" class="text-sm text-ink-gray-5">View only</span>
			<span v-if="canWrite && dirty" class="text-sm text-ink-gray-5 max-sm:hidden"
				>Unsaved changes</span
			>
			<Button
				v-for="action in actions"
				:key="action.label"
				:label="action.label"
				:loading="running === action.label"
				:disabled="dirty"
				:title="dirty ? 'Save first' : ''"
				@click="runAction(action)"
			/>
			<Dropdown v-if="canDelete" align="end" :options="menu">
				<template #trigger>
					<button class="flow-icon-btn" title="More">
						<span class="lucide-ellipsis size-4" aria-hidden="true" />
					</button>
				</template>
			</Dropdown>
			<Button
				v-if="canWrite && doc"
				variant="solid"
				:label="isNew ? 'Create' : 'Save'"
				:loading="saving"
				:disabled="!dirty"
				@click="save"
			/>
		</template>
	</PageHeader>
	<div class="min-h-0 flex-1 overflow-y-auto">
		<form
			v-if="doc"
			ref="form"
			class="mx-auto w-full max-w-[800px] px-4 pb-16 pt-6 sm:px-6"
			@submit.prevent="save"
		>
			<p
				v-if="doc.is_system_generated && canWrite"
				class="mb-5 rounded-5 bg-surface-gray-2 px-3 py-2 text-sm leading-5 text-ink-gray-7"
			>
				Comes with an app, so greyed-out fields can't be changed.
			</p>
			<div class="flex flex-col gap-5">
				<div v-for="field in fields" :key="field.name" class="min-w-0">
					<FieldControl
						v-if="canWrite"
						:field="field"
						:doc="doc"
						:disabled="isLocked(field)"
					/>
					<!-- one who may only read it sees its values, not disabled inputs -->
					<div v-else class="flex flex-col gap-1.5">
						<span class="text-sm text-ink-gray-5">{{ field.label }}</span>
						<span
							v-if="field.type === 'multilink' && doc[field.name]?.length"
							class="flex flex-wrap gap-1.5"
						>
							<span
								v-for="item in doc[field.name]"
								:key="item"
								class="rounded-4 bg-surface-gray-2 px-2 py-0.5 text-base text-ink-gray-8"
								>{{ item }}</span
							>
						</span>
						<span
							v-else
							class="whitespace-pre-wrap break-words text-base leading-6"
							:class="[
								shown(field) ? 'text-ink-gray-8' : 'text-ink-gray-4',
								field.type === 'code' && 'font-mono text-sm',
							]"
							>{{ shown(field) || "None" }}</span
						>
					</div>
				</div>
			</div>
		</form>
		<p v-else-if="error" class="px-6 py-16 text-center text-base text-ink-gray-5">{{ error }}</p>
		<LoadingState v-else class="h-full justify-center text-sm text-ink-gray-5" />
	</div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, watch } from "vue";
import { useRouter } from "vue-router";
import { Button, dialog, toast } from "frappe-ui";
import Dropdown from "frappe-ui/src/components/Dropdown/Dropdown.vue";
import LoadingState from "@flow/ui-core/components/LoadingState.vue";

import FieldControl from "../settings/FieldControl.vue";
import { useRecord } from "../settings/records.js";
import PageHeader from "./PageHeader.vue";

// A record's page: its fields in the column, its actions in the bar. Leaving it
// with edits unsaved asks first.
const props = defineProps({
	spec: { type: Object, required: true },
	info: { type: Object, required: true }, // the page's entry in FORMS
	name: { type: String, default: null }, // null for a new record
});
const leavePage = inject("leavePage");
const router = useRouter();

let leaving = false; // a deleted record's page goes without asking
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
} = useRecord(props, (event, saved) => {
	// a new or renamed record takes its old address's place
	if (event === "saved" && saved.name !== props.name)
		router.replace({ name: "records", params: { kind: props.spec.key, record: saved.name } });
	if (event === "deleted") {
		leaving = true;
		leavePage();
	}
});
// the bar has no room for a failure's reason: it pops up instead, unless the record never loaded
watch(error, (message) => message && doc.value && toast.error(message));

// a reader's fields leave out the name, which the bar shows
const fields = computed(() =>
	visibleFields.value.filter((field) => canWrite.value || !field.rename)
);

// a field's value as read: numbers with separators, an unset number its placeholder ("No limit")
function shown(field) {
	const value = doc.value[field.name];
	if (field.type === "check") return value ? "Yes" : "No";
	if (field.type === "int") return value ? value.toLocaleString() : field.placeholder ?? "0";
	return value == null ? "" : String(value);
}

const menu = computed(() => [
	{ label: "Delete", icon: "lucide-trash-2", theme: "red", onClick: remove },
]);

function discard() {
	return new Promise((resolve) => {
		dialog.confirm({
			title: "Discard changes?",
			size: "lg",
			message: `Your changes to this ${props.spec.singular} are not saved.`,
			actions: [
				{ label: "Keep editing", variant: "outline", onClick: () => resolve(false) },
				{ label: "Discard", variant: "solid", theme: "red", onClick: () => resolve(true) },
			],
			onCancel: () => resolve(false),
		});
	});
}
const unguard = router.beforeEach(() => leaving || !dirty.value || discard());
function onUnload(event) {
	if (dirty.value) event.preventDefault();
}
window.addEventListener("beforeunload", onUnload);
onBeforeUnmount(() => {
	unguard();
	window.removeEventListener("beforeunload", onUnload);
});
</script>
