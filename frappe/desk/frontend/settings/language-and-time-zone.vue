<!-- The person's language and time zone. The time zones come from the server, which a generated row cannot ask for. -->
<template>
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
				@change="commit(field.fieldname)"
			/>
		</SettingsRow>
		<ErrorMessage
			v-if="refused[field.fieldname]"
			class="-mt-1.5 pb-3.5"
			:message="refused[field.fieldname]"
		/>
	</div>
</template>

<script lang="ts">
import { runMethod } from "@framework/ui/api";

let zones: Promise<string[]> | undefined;

/** The server's time zones, read once while the desk is open; a failed read is not kept. */
function zoneList(): Promise<string[]> {
	zones ??= runMethod<{ timezones: string[] }>(
		"frappe.core.doctype.user.user.get_timezones",
		{},
		{ http: "GET" }
	).then(
		({ data }) => data.timezones,
		() => ((zones = undefined), [])
	);
	return zones;
}
</script>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ErrorMessage, SettingsRow, Skeleton } from "frappe-ui";
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
zoneList().then((zones) => (timeZones.value = zones));

const fields = computed(() => [
	{ fieldname: "language", fieldtype: "Link", options: "Language", label: __("Language") },
	{
		fieldname: "time_zone",
		fieldtype: "Autocomplete",
		options: [...new Set([user.doc.time_zone, ...timeZones.value])].filter(Boolean).join("\n"),
		label: __("Time Zone"),
	},
]);

const refused = reactive<Record<string, string>>({});

/** The binding's error belongs to the whole draft, so it shows under the row whose save it followed. */
async function commit(fieldname: string) {
	await user.commit();
	refused[fieldname] = user.error;
}
</script>
