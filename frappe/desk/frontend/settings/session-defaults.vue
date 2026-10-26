<!-- The person's session defaults: one Link per doctype the site's Session Default Settings lists. -->
<template>
	<p v-if="failed" class="py-3.5 text-base text-ink-red-7">
		{{ __("Session defaults could not load") }}
	</p>
	<div v-else-if="!fields" aria-hidden="true">
		<div class="flex items-center gap-8 py-3.5">
			<Skeleton class="h-4 w-36 rounded-1" />
			<Skeleton class="ml-auto h-7 w-56 rounded-4" />
		</div>
	</div>
	<p v-else-if="!fields.length" class="py-3.5 text-base text-ink-gray-6">
		{{ __("This site sets no session defaults.") }}
	</p>
	<div
		v-for="field in fields"
		v-else
		:key="field.fieldname"
		:data-fieldname="field.fieldname"
		class="border-b border-outline-gray-1 last:border-b-0"
	>
		<SettingsRow :title="field.label">
			<component
				:is="getFieldComponent('Link')"
				class="w-56"
				:field="{ ...field, label: '' }"
				:model-value="values[field.fieldname]"
				@update:model-value="(value: string | null) => (values[field.fieldname] = value)"
				@change="save"
			/>
		</SettingsRow>
	</div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { SettingsRow, Skeleton, toast } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import { getFieldComponent } from "@framework/ui/FormLayout";
import { __ } from "frappe/i18n";

/** A block with no binding is handed an empty `bindings`. */
defineProps<{ bindings: Record<string, never> }>();

const METHOD = "frappe.core.doctype.session_default_settings.session_default_settings";

interface DefaultField {
	fieldname: string;
	fieldtype: "Link";
	options: string;
	label: string;
	default: string | null;
}

const fields = ref<DefaultField[] | null>(null);
const failed = ref(false);
const values = reactive<Record<string, string | null>>({});

runMethod<string>(`${METHOD}.get_session_default_values`, {}, { http: "GET" }).then(
	({ data }) => {
		const read: DefaultField[] = JSON.parse(data);
		for (const field of read) values[field.fieldname] = field.default || null;
		fields.value = read;
	},
	() => (failed.value = true)
);

async function save() {
	const default_values = Object.fromEntries(
		Object.entries(values).map(([fieldname, value]) => [fieldname, value || ""])
	);
	const saved = await runMethod<string | null>(
		`${METHOD}.set_session_default_values`,
		{ default_values },
		{ nullable: true }
	).then(
		({ data }) => data === "success",
		() => false
	);
	if (!saved) toast.error(__("Your session defaults did not save"));
}
</script>
