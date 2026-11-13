<template>
	<form class="flex flex-col gap-4" @submit.prevent="save">
		<FormControl
			v-model="password"
			:type="shown ? 'text' : 'password'"
			variant="outline"
			size="md"
			autocomplete="new-password"
			:label="text.label"
			:placeholder="text.placeholder"
			:description="text.hint"
			autofocus
		>
			<template #suffix>
				<button
					type="button"
					class="-me-1 flex size-6 items-center justify-center rounded text-ink-gray-5 hover:text-ink-gray-8"
					:aria-label="shown ? text.hide : text.show"
					:aria-pressed="shown"
					@click="shown = !shown"
				>
					<span :class="shown ? 'lucide-eye-off' : 'lucide-eye'" class="size-4" />
				</button>
			</template>
		</FormControl>
		<Button
			type="submit"
			variant="solid"
			class="self-end"
			:label="text.save"
			:loading="saving"
			:disabled="password.length < 8"
		/>
		<ErrorMessage :message="error" />
	</form>
</template>

<script setup lang="ts">
import { Button, ErrorMessage, FormControl, call } from "frappe-ui";
import { computed, ref } from "vue";

/** English defaults; pass translated text to relabel. */
export interface PasswordStepLabels {
	label: string;
	placeholder: string;
	hint: string;
	show: string;
	hide: string;
	save: string;
	failed: string;
}

const props = defineProps<{ labels?: Partial<PasswordStepLabels> }>();
const emit = defineEmits<{ done: [] }>();

const defaults: PasswordStepLabels = {
	label: "Password",
	placeholder: "At least 8 characters",
	hint: "You are signed in, but have no password yet. Set one so you can sign in again from any device.",
	show: "Show",
	hide: "Hide",
	save: "Save and continue",
	failed: "That password could not be saved. Try another.",
};
const text = computed(() => ({ ...defaults, ...props.labels }));

const password = ref("");
const shown = ref(false);
const saving = ref(false);
const error = ref("");

async function save() {
	if (password.value.length < 8) return;
	saving.value = true;
	error.value = "";
	try {
		await call("frappe.core.doctype.user.user.set_first_password", {
			new_password: password.value,
		});
		password.value = "";
		emit("done");
	} catch (e: unknown) {
		const messages = (e as { messages?: string[] })?.messages;
		error.value = messages?.[0] || text.value.failed;
	} finally {
		saving.value = false;
	}
}
</script>
