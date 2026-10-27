<!-- The confirmation before a log out, on a boolean. A failure is toasted and keeps the dialog. -->
<template>
	<Dialog
		v-model="open"
		:title="__('Log out?')"
		:message="__('You will need to sign in again.')"
		size="sm"
		:actions="actions"
	/>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Dialog, toast } from "frappe-ui";
import { __ } from "@/i18n";
import { logout } from "./session";

const open = defineModel<boolean>({ default: false });

// `Dialog` awaits an action and shows its loading state itself.
const actions = computed(() => [
	{ label: __("Cancel"), onClick: () => (open.value = false) },
	{ label: __("Log out"), variant: "outline", theme: "red", onClick: confirm },
]);

async function confirm() {
	try {
		await logout();
	} catch {
		toast.error(__("Could not log out"));
	}
}
</script>
