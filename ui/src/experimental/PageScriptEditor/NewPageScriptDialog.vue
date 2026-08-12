<template>
	<Dialog v-model="isOpen" :options="{ title: 'New page script' }">
		<template #body-content>
			<div class="flex flex-col gap-4">
				<FormControl
					v-model="name"
					label="Name"
					placeholder="deal-hello"
					description="Names the script in stack traces, as page-script/<name>.js. It cannot be changed later."
					autocomplete="off"
					@keyup.enter="submit"
				/>
				<ErrorMessage :message="error" />
			</div>
		</template>
		<template #actions>
			<Button
				class="w-full"
				variant="solid"
				label="Create"
				:loading="creating"
				:disabled="!name.trim()"
				@click="submit"
			/>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
// Page Script is `autoname: prompt`, so a new script needs a name before it can
// exist at all — hence a dialog rather than an inline "Untitled" row.
import { ref, watch } from "vue";
import { Button, Dialog, ErrorMessage, FormControl } from "frappe-ui";
import { errorMessage } from "../errorMessage";

const props = defineProps<{
	/** Names already taken, for a pre-check; the primary key is the real guard. */
	taken: string[];
	onSubmit: (name: string) => Promise<unknown>;
}>();

const isOpen = defineModel<boolean>({ default: false });

const name = ref("");
const creating = ref(false);
const error = ref("");

watch(isOpen, (open) => {
	if (!open) return;
	name.value = "";
	error.value = "";
});

async function submit() {
	const value = name.value.trim();
	if (!value || creating.value) return;
	if (props.taken.includes(value)) {
		error.value = `A script named "${value}" already exists.`;
		return;
	}

	creating.value = true;
	error.value = "";
	try {
		await props.onSubmit(value);
		isOpen.value = false;
	} catch (exception) {
		error.value = errorMessage(exception);
	} finally {
		creating.value = false;
	}
}
</script>
