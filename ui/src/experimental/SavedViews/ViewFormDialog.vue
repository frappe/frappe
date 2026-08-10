<template>
	<Dialog v-model="isOpen" :options="{ title }">
		<template #body-content>
			<div class="flex flex-col gap-4">
				<IconLabelField
					v-model:text="label"
					v-model:icon="icon"
					label="View Name"
					placeholder="Open deals"
					@submit="submit"
				/>
				<FormControl
					v-if="canShare && !view"
					v-model="shared"
					type="checkbox"
					label="Share with everyone"
					description="Shared views live in the team's section and only a manager can change them."
				/>
				<ErrorMessage :message="error" />
			</div>
		</template>
		<template #actions>
			<Button
				class="w-full"
				variant="solid"
				:label="view ? 'Save' : 'Create'"
				:loading="saving"
				:disabled="!label.trim()"
				@click="submit"
			/>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { Button, Dialog, ErrorMessage, FormControl } from "frappe-ui";
import { IconLabelField } from "../IconPicker";
import { errorMessage } from "../errorMessage";
import type { SavedView, ViewFormValues } from "./types";

const props = defineProps<{
	view?: SavedView | null;
	canShare?: boolean;
	onSubmit: (values: ViewFormValues) => Promise<unknown>;
}>();

const isOpen = defineModel<boolean>({ default: false });

const label = ref("");
const icon = ref<string | null>("");
const shared = ref(false);

const saving = ref(false);
const error = ref("");

const title = computed(() => (props.view ? "Edit view" : "Create view"));

watch(isOpen, (open) => {
	if (!open) return;
	label.value = props.view?.label ?? "";
	icon.value = (props.view?.icon ?? "").replace(/^lucide-/, "");
	shared.value = false;
	error.value = "";
});

async function submit() {
	if (!label.value.trim() || saving.value) return;

	saving.value = true;
	error.value = "";
	try {
		await props.onSubmit({
			label: label.value.trim(),
			icon: (icon.value ?? "").trim(),
			shared: shared.value,
		});
		isOpen.value = false;
	} catch (exception) {
		error.value = errorMessage(exception);
	} finally {
		saving.value = false;
	}
}
</script>
