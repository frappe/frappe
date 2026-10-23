<template>
	<FormControl
		v-if="field.type === 'readonly'"
		:type="readonlyText.includes('\n') || readonlyText.length > 80 ? 'textarea' : 'text'"
		variant="outline"
		:label="field.label"
		:description="field.description"
		:model-value="readonlyText"
		disabled
	/>

	<!-- the switch centred on the label and its description, not on the label alone -->
	<label v-else-if="field.type === 'check'" class="flex items-center justify-between gap-4">
		<span class="flex flex-col gap-1">
			<span data-slot="label" class="text-sm leading-tighter text-ink-gray-6">{{
				field.label
			}}</span>
			<span v-if="field.description" class="text-xs text-ink-gray-5">{{
				field.description
			}}</span>
		</span>
		<Switch
			size="sm"
			:model-value="!!doc[field.name]"
			:disabled="disabled"
			@update:model-value="(value) => (doc[field.name] = value ? 1 : 0)"
		/>
	</label>

	<div v-else-if="field.type === 'code'" class="flex flex-col gap-1">
		<FormLabel :label="field.label" :required="field.required" />
		<CodeField
			:model-value="doc[field.name] ?? ''"
			:language="field.language"
			:placeholder="field.placeholder"
			:disabled="disabled"
			@update:model-value="(value) => (doc[field.name] = value)"
		/>
		<span v-if="field.description" class="text-2xs text-ink-gray-5">{{
			field.description
		}}</span>
	</div>

	<div v-else-if="field.type === 'attach'" class="flex flex-col gap-1">
		<FormLabel :label="field.label" :required="field.required" />
		<div class="flex min-w-0 items-center gap-3">
			<FileUploader
				:file-types="fileTypes"
				:private="true"
				@success="(file) => (doc[field.name] = file.file_url)"
			>
				<template #default="{ openFileSelector, uploading, progress }">
					<Button
						variant="outline"
						:loading="uploading"
						:label="
							uploading
								? `Uploading ${progress}%`
								: doc[field.name]
								? 'Replace file'
								: 'Upload file'
						"
						:disabled="disabled"
						@click="openFileSelector"
					/>
				</template>
			</FileUploader>
			<a
				v-if="doc[field.name]"
				:href="doc[field.name]"
				target="_blank"
				class="truncate text-xs text-ink-gray-7 underline"
			>
				{{ fileName }}
			</a>
		</div>
	</div>

	<FormControl
		v-else-if="field.type === 'link'"
		type="combobox"
		variant="outline"
		:label="field.label"
		:description="field.description"
		:required="field.required"
		:options="options"
		v-model:query="linkQuery"
		:filterable="false"
		:loading="linksLoading"
		:error="linksError"
		:model-value="doc[field.name] || null"
		:disabled="disabled"
		placeholder="Select…"
		@update:model-value="(value) => (doc[field.name] = value ?? '')"
	/>

	<!-- read-only, it still opens to show what is picked, with nothing to change -->
	<FormControl
		v-else-if="field.type === 'multilink'"
		type="multiselect"
		variant="outline"
		:label="field.label"
		:description="field.description"
		:options="disabled ? picked : options"
		v-model:query="linkQuery"
		:filterable="false"
		:hide-search="disabled"
		:loading="linksLoading"
		:error="linksError"
		:model-value="doc[field.name] ?? []"
		placeholder="Select…"
		@update:model-value="(value) => (doc[field.name] = value ?? [])"
	>
		<template v-if="disabled" #footer />
	</FormControl>

	<FormControl
		v-else-if="field.type === 'select'"
		type="select"
		variant="outline"
		:label="field.label"
		:description="field.description"
		:required="field.required"
		:options="field.options"
		:model-value="doc[field.name]"
		:disabled="disabled"
		@update:model-value="(value) => (doc[field.name] = value)"
	/>

	<!-- the menu opens under the input rather than over it -->
	<FormControl
		v-else-if="field.type === 'provider'"
		type="select"
		variant="outline"
		:label="field.label"
		:description="field.description"
		:required="field.required"
		:options="providerOptions"
		:model-value="doc[field.name] || null"
		:disabled="disabled"
		placeholder="Select…"
		side="bottom"
		@update:model-value="(value) => (doc[field.name] = value ?? '')"
	/>

	<FormControl
		v-else-if="field.type === 'textarea'"
		type="textarea"
		variant="outline"
		:label="field.label"
		:description="field.description"
		:required="field.required"
		:rows="field.rows ?? 4"
		:placeholder="field.placeholder"
		:model-value="doc[field.name] ?? ''"
		:disabled="disabled"
		@update:model-value="(value) => (doc[field.name] = value)"
	/>

	<!-- with a provider, its models are offered; any other id can still be typed -->
	<FormControl
		v-else-if="field.type === 'model_id' && (modelsLoading || known.length)"
		type="combobox"
		variant="outline"
		:label="field.label"
		:description="field.description"
		:required="field.required"
		:placeholder="field.placeholder"
		v-model:query="typed"
		:filterable="false"
		:loading="modelsLoading"
		:options="modelOptions"
		:model-value="doc[field.name] || null"
		:disabled="disabled"
		@update:model-value="pickModel"
	/>

	<FormControl
		v-else
		:type="inputType"
		variant="outline"
		:label="field.label"
		:description="field.description"
		:required="field.required"
		:placeholder="field.placeholder"
		:model-value="inputValue"
		:disabled="disabled"
		@update:model-value="
			(value) => (doc[field.name] = field.type === 'int' ? Number(value) || 0 : value)
		"
	/>
</template>

<script setup>
import { computed, defineAsyncComponent, inject, ref, watch } from "vue";
import { Button, FileUploader, FormControl, FormLabel, Switch } from "frappe-ui";

import { useDebouncedValue } from "@flow/ui-core/debounce.js";

import { call } from "../api/frappe.js";
import { searchLinks } from "./links.js";

// CodeMirror loads only when a code field shows
const CodeField = defineAsyncComponent(() => import("./CodeField.vue"));

const props = defineProps({
	field: { type: Object, required: true },
	doc: { type: Object, required: true },
	disabled: { type: Boolean, default: false },
});
const page = inject("flowPage");

// numbers read with separators; everything else as it is
const readonlyText = computed(() => {
	const value = props.doc[props.field.name];
	if (value == null || value === "") return "";
	return typeof value === "number" ? value.toLocaleString() : String(value);
});

const inputType = computed(
	() => ({ int: "number", password: "password", url: "url" }[props.field.type] ?? "text")
);

// an int's placeholder stands for 0, e.g. "No limit"
const inputValue = computed(() => {
	const value = props.doc[props.field.name];
	if (props.field.type === "int" && props.field.placeholder && !value) return "";
	return value ?? "";
});

// a saved provider the list leaves out still shows as itself
const providerOptions = computed(() => {
	const value = props.doc[props.field.name];
	const options = props.field.options;
	return !value || options.some((option) => option.value === value)
		? options
		: [...options, { label: value, value }];
});

// The current options stay while another query loads; selected values are always offered.
// A read-only field searches only for its values' labels, so not where the search is refused:
// it shows the names as they are.
const linkQuery = ref("");
const debouncedLinkQuery = useDebouncedValue(linkQuery, 300);
const searched = computed(() =>
	props.disabled && !page.can(props.field.link, "read") ? null : props.field.link
);
const links = ref([]);
const linksLoading = ref(!!searched.value); // until the first results arrive
const linksError = ref("");
const options = computed(() => {
	const value = props.doc[props.field.name];
	const selected = Array.isArray(value) ? value : value ? [value] : [];
	return [
		...links.value,
		...selected
			.filter((name) => !links.value.some((option) => option.value === name))
			.map((name) => ({ value: name, label: name })),
	];
});
// a read-only multi-link lists only its picks, each disabled
const picked = computed(() =>
	(props.doc[props.field.name] ?? []).map((name) => ({
		...options.value.find((option) => option.value === name),
		disabled: true,
	}))
);
watch(
	[searched, debouncedLinkQuery],
	async ([doctype, query], _, onCleanup) => {
		let stale = false;
		onCleanup(() => (stale = true));
		linksError.value = "";
		if (!doctype) {
			linksLoading.value = false;
			return;
		}
		try {
			const data = await searchLinks(doctype, query, props.doc.doctype);
			if (!stale) links.value = data;
		} catch (err) {
			if (!stale) linksError.value = err.message;
		} finally {
			if (!stale) linksLoading.value = false;
		}
	},
	{ immediate: true }
);

// a linked provider's models (ids with its prefix), offered in the model id dropdown;
// an answer for a provider no longer picked is dropped
const known = ref([]);
const modelsLoading = ref(false);
watch(
	() => (props.field.type === "model_id" && !props.disabled ? props.doc.provider : null),
	async (provider, _, onCleanup) => {
		let stale = false;
		onCleanup(() => (stale = true));
		known.value = [];
		modelsLoading.value = !!provider;
		if (!provider) return;
		const models = await call("frappe.flow.doctype.flow_model.flow_model.get_provider_models", {
			provider,
		}).catch(() => []);
		if (stale) return;
		// no list means a plain input: keep what was typed meanwhile
		if (!models.length && typed.value.trim()) pickModel(typed.value.trim());
		known.value = models;
		modelsLoading.value = false;
	},
	{ immediate: true }
);
// the list is filtered here, a beat after typing, rather than on every keystroke
const typed = ref("");
const debouncedTyped = useDebouncedValue(typed, 150);
const modelOptions = computed(() => {
	const q = debouncedTyped.value.trim().toLowerCase();
	const prefix = `${props.doc.provider}/`;
	return [
		...known.value
			.map((model) => ({ label: model.slice(prefix.length), value: model }))
			.filter((option) => !q || option.label.toLowerCase().includes(q)),
		{
			type: "custom",
			key: "typed",
			label: "Use the typed id",
			condition: ({ query }) =>
				!!query.trim() && !known.value.includes(prefix + query.trim()),
			onClick: ({ query }) => pickModel(query.trim()),
		},
	];
});
function pickModel(value) {
	props.doc[props.field.name] = value ?? "";
	typed.value = "";
}

const fileTypes = computed(() =>
	(page.state.boot.file_types ?? []).map((ext) => `.${ext}`).join(",")
);
const fileName = computed(() =>
	String(props.doc[props.field.name] ?? "")
		.split("/")
		.pop()
);
</script>
