<!-- The person's own password: the current one, a new one the site's policy accepts, then a reload. -->
<template>
	<form @submit.prevent="change">
		<div
			v-for="row in ROWS"
			:key="row.key"
			:data-fieldname="row.key"
			class="border-b border-outline-gray-1 last:border-b-0"
		>
			<SettingsRow :title="row.title">
				<Password
					v-model="values[row.key]"
					class="w-56"
					:autocomplete="row.autocomplete"
					:error="row.key === 'confirm' ? mismatch : undefined"
				/>
			</SettingsRow>
		</div>
		<div class="flex items-start gap-8 py-3.5">
			<ErrorMessage class="min-w-0 flex-1" :message="failure" />
			<Button
				class="ml-auto"
				type="submit"
				variant="solid"
				:label="__('Change password')"
				:disabled="!ready"
				:loading="changing"
			/>
		</div>
	</form>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { Button, ErrorMessage, Password, SettingsRow } from "frappe-ui";
import { runMethod } from "@framework/ui/api";
import { __ } from "frappe/i18n";

/** A block with no binding is handed an empty `bindings`. */
defineProps<{ bindings: Record<string, never> }>();

const UPDATE_PASSWORD = "frappe.core.doctype.user.user.update_password";

const ROWS = [
	{ key: "current", title: __("Current password"), autocomplete: "current-password" },
	{ key: "next", title: __("New password"), autocomplete: "new-password" },
	{ key: "confirm", title: __("Confirm new password"), autocomplete: "new-password" },
] as const;

const values = reactive({ current: "", next: "", confirm: "" });
const failure = ref("");
const changing = ref(false);

const mismatch = computed(() =>
	values.confirm && values.confirm !== values.next
		? __("The new passwords do not match")
		: undefined
);
const ready = computed(() => !!values.current && !!values.next && values.confirm === values.next);

async function change() {
	if (!ready.value || changing.value) return;
	changing.value = true;
	failure.value = "";
	try {
		await runMethod(UPDATE_PASSWORD, {
			old_password: values.current,
			new_password: values.next,
			logout_all_sessions: 1,
		});
	} catch (error) {
		failure.value = error instanceof Error ? error.message : String(error);
		changing.value = false;
		return;
	}
	// The server starts a new session, so this page's CSRF token is stale until it loads again.
	window.location.reload();
}
</script>
