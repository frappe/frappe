<template>
	<div>
		<Checkbox :model-value="enabled" :label="label" @update:model-value="save" />
		<ErrorMessage class="mt-1" :message="error" />
	</div>
</template>

<script setup lang="ts">
import { Checkbox, ErrorMessage, call } from "frappe-ui";
import { onMounted, ref } from "vue";
import { useTelemetry } from "../../telemetry";

// The desk wizard asks this on its first slide; an app that skips the wizard asks here.
const props = withDefaults(
	defineProps<{ appName: string; label?: string; errorMessage?: string }>(),
	{
		label: "Share usage data",
		errorMessage: "Could not save your choice. Please try again.",
	}
);

const telemetry = useTelemetry();
const enabled = ref(true);
const saving = ref(false);
const error = ref("");

onMounted(async () => {
	const value = await call("frappe.client.get_single_value", {
		doctype: "System Settings",
		field: "enable_telemetry",
	}).catch(() => 1);
	if (!saving.value) enabled.value = Boolean(Number(value));
});

async function save(share: boolean) {
	if (saving.value) return;
	enabled.value = share;
	saving.value = true;
	error.value = "";
	try {
		await call("frappe.client.set_value", {
			doctype: "System Settings",
			name: "System Settings",
			fieldname: "enable_telemetry",
			value: share ? 1 : 0,
		});
	} catch (err) {
		enabled.value = !share;
		error.value = props.errorMessage;
		console.error(err);
		return;
	} finally {
		saving.value = false;
	}
	if (share) telemetry.enable({ app_name: props.appName });
	else telemetry.disable();
}
</script>
