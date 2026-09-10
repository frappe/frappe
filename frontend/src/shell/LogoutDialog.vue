<!-- The confirmation before a log out, on a boolean. A failure is toasted and keeps the dialog. -->
<template>
	<Dialog
		v-model="open"
		title="Log out?"
		message="You will need to sign in again."
		size="sm"
		:actions="actions"
	/>
</template>

<script setup lang="ts">
import { Dialog, toast } from "frappe-ui";
import { logout } from "./session";

const open = defineModel<boolean>({ default: false });

// `Dialog` awaits an action and shows its loading state itself.
const actions = [
	{ label: "Cancel", onClick: () => (open.value = false) },
	{ label: "Log out", variant: "outline", theme: "red", onClick: confirm },
];

async function confirm() {
	try {
		await logout();
	} catch {
		toast.error("Could not log out");
	}
}
</script>
