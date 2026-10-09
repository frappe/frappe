<template>
	<SettingsPage :title="title" :description="description" :back="back" @back="emit('close')">
		<template v-if="doc && enabledField" #actions>
			<label class="flex items-center gap-2 text-sm text-ink-gray-7">
				Enabled
				<Switch
					size="sm"
					:model-value="!!doc.enabled"
					:disabled="!canWrite || isLocked(enabledField)"
					@update:model-value="(value) => (doc.enabled = value ? 1 : 0)"
				/>
			</label>
		</template>
		<slot />
		<form v-if="doc" class="mt-2 flex flex-col gap-4" @submit.prevent="save">
			<div
				v-if="doc.is_system_generated"
				class="rounded-6 border border-outline-gray-2 bg-surface-gray-1 px-3 py-2 text-xs text-ink-gray-7"
			>
				Defined in code. Only what code leaves open can change here.
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
			<Button v-if="!spec.single" variant="outline" label="Cancel" @click="emit('close')" />
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
import { computed, inject, onBeforeUnmount, onMounted, ref } from "vue";
import { Button, ErrorMessage, Switch, dialog, toast } from "frappe-ui";
import LoadingState from "@flow/ui-core/components/LoadingState.vue";
import SettingsPage from "@flow/ui-core/components/SettingsPage.vue";

import { call } from "../api/frappe.js";
import FieldControl from "./FieldControl.vue";
import { newDoc } from "./specs.js";

// One document of the spec's doctype, as a settings page: loaded by name (or the single),
// or a blank new one. Multi-link fields are edited as name lists and written back as child
// rows. The default slot renders above the fields, for a page's own tabs.
const props = defineProps({
	spec: { type: Object, required: true },
	name: { type: String, default: null },
	title: { type: String, required: true },
	description: { type: String, default: "" },
	back: { type: String, default: "" }, // the way back to a list, when there is one
});
const emit = defineEmits(["saved", "deleted", "close"]);
const page = inject("flowPage");

const doc = ref(null);
const original = ref("");
const error = ref("");
const saving = ref(false);
const running = ref(null);

const isNew = computed(() => !props.spec.single && !doc.value?.name);
const canWrite = computed(() => page.can(props.spec.doctype, isNew.value ? "create" : "write"));
const canDelete = computed(
	() => !isNew.value && !props.spec.single && page.can(props.spec.doctype, "delete")
);
const dirty = computed(() => JSON.stringify(doc.value) !== original.value);
// the enabled flag sits beside the heading rather than among the fields
const enabledField = computed(() => props.spec.fields.find((field) => field.name === "enabled"));
const visibleFields = computed(() =>
	props.spec.fields.filter(
		(field) => field !== enabledField.value && (!field.when || field.when(doc.value))
	)
);
const actions = computed(() =>
	(props.spec.actions ?? []).filter((action) => !action.when || action.when(doc.value))
);
const multilinks = computed(() => props.spec.fields.filter((field) => field.type === "multilink"));

function isLocked(field) {
	return !!field.locked?.(doc.value);
}

function adopt(data) {
	const value = { ...data };
	for (const field of multilinks.value)
		value[field.name] = (data[field.name] ?? []).map((row) => row[field.child]);
	doc.value = value;
	original.value = JSON.stringify(value);
}

async function load() {
	error.value = "";
	try {
		if (props.spec.single)
			adopt(await call("frappe.client.get", { doctype: props.spec.doctype }));
		else if (props.name)
			adopt(
				await call("frappe.client.get", { doctype: props.spec.doctype, name: props.name })
			);
		else adopt(newDoc(props.spec));
	} catch (err) {
		error.value = err.message;
	}
}
onMounted(load);

// Cmd+S / Ctrl+S saves, as in the Desk
function onKey(event) {
	if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
		event.preventDefault();
		if (canWrite.value) save();
	}
}
onMounted(() => window.addEventListener("keydown", onKey));
onBeforeUnmount(() => window.removeEventListener("keydown", onKey));

function payload() {
	const value = { ...doc.value, doctype: props.spec.doctype };
	for (const field of multilinks.value)
		value[field.name] = (doc.value[field.name] ?? []).map((name) => ({ [field.child]: name }));
	// a JSON column rejects "": an empty editor means no value at all
	for (const field of props.spec.fields)
		if (field.language === "json" && !value[field.name]) value[field.name] = null;
	return value;
}

async function save() {
	if (saving.value || !dirty.value) return;
	saving.value = true;
	error.value = "";
	try {
		const method = isNew.value ? "frappe.client.insert" : "frappe.client.save";
		const saved = await call(method, { doc: payload() });
		adopt(saved);
		page.changed(props.spec.doctype);
		toast.success(isNew.value ? "Created" : "Saved");
		emit("saved", saved);
	} catch (err) {
		error.value = err.message;
	} finally {
		saving.value = false;
	}
}

function remove() {
	dialog.danger({
		title: `Delete this ${props.spec.singular}?`,
		message: `“${
			doc.value[props.spec.titleField] || doc.value.name
		}” will be permanently removed.`,
		onConfirm: async ({ close }) => {
			try {
				await call("frappe.client.delete", {
					doctype: props.spec.doctype,
					name: doc.value.name,
				});
				page.changed(props.spec.doctype);
				toast.success("Deleted");
				close();
				emit("deleted");
			} catch (err) {
				error.value = err.message;
				close();
			}
		},
	});
}

// a doc method's answer; frappe returns the whole body when it also sends docs
async function runAction(action) {
	running.value = action.label;
	error.value = "";
	try {
		const result = await call("run_doc_method", {
			dt: props.spec.doctype,
			dn: doc.value.name,
			method: action.method,
			args: action.args ?? {},
		});
		const message = result?.docs ? result.message : result;
		toast.success(message?.message ?? action.success ?? "Done");
		await load();
	} catch (err) {
		error.value = err.message;
	} finally {
		running.value = null;
	}
}
</script>
