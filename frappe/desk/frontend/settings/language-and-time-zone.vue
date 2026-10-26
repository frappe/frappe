<!-- The person's language and time zone. The time zones come from the server, which a generated row cannot ask for. -->
<template>
	<p v-if="user.error" class="py-3.5 text-base text-ink-red-7">{{ user.error }}</p>
	<div
		v-for="field in fields"
		:key="field.fieldname"
		:data-fieldname="field.fieldname"
		class="border-b border-outline-gray-1 last:border-b-0"
	>
		<SettingsRow :title="field.label">
			<Skeleton v-if="user.loading" class="h-7 w-56 rounded-4" />
			<component
				:is="getFieldComponent(field.fieldtype)"
				v-else
				class="w-56"
				:field="{ ...field, label: '' }"
				:model-value="user.doc[field.fieldname]"
				@update:model-value="(value: unknown) => (user.doc[field.fieldname] = value)"
				@change="user.commit()"
			/>
		</SettingsRow>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { SettingsRow, Skeleton } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import { getFieldComponent } from "@framework/ui/FormLayout";
import { __ } from "frappe/i18n";

/** The part of the settings dialog's binding this block reads; the full shape is `ComponentBinding`. */
interface Binding {
	readonly doc: Record<string, any>;
	readonly loading: boolean;
	readonly error: string;
	commit(): Promise<void>;
}

const props = defineProps<{ bindings: { user: Binding } }>();
const user = props.bindings.user;

const timeZones = ref<string[]>([]);
runMethod<{ timezones: string[] }>(
	"frappe.core.doctype.user.user.get_timezones",
	{},
	{ http: "GET" }
)
	.then(({ data }) => (timeZones.value = data.timezones))
	.catch(() => (timeZones.value = [user.doc.time_zone].filter(Boolean)));

const fields = computed(() => [
	{ fieldname: "language", fieldtype: "Link", options: "Language", label: __("Language") },
	{
		fieldname: "time_zone",
		fieldtype: "Autocomplete",
		options: timeZones.value.join("\n"),
		label: __("Time Zone"),
	},
]);
</script>
