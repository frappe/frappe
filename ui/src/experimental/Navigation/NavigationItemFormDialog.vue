<template>
	<Dialog v-model="isOpen" :options="{ title: `${verb} ${kind.label.toLowerCase()}` }">
		<template #body-content>
			<div class="flex flex-col gap-4">
				<Link
					v-if="kind.doctype"
					v-model="target"
					:doctype="kind.doctype"
					:filters="kind.filters"
					:label="kind.label"
					:placeholder="kind.placeholder"
				/>
				<FormControl
					v-else
					v-model="target"
					:label="kind.label"
					:placeholder="kind.placeholder"
					autocomplete="off"
					@keydown.enter="submit"
				/>

				<IconLabelField
					v-model:text="label"
					v-model:icon="icon"
					label="Label"
					placeholder="Documentation"
					@submit="submit"
				/>

				<ErrorMessage :message="error" />
			</div>
		</template>
		<template #actions>
			<Button
				class="w-full"
				variant="solid"
				:label="initial ? 'Save' : 'Add'"
				:loading="saving"
				:disabled="!isComplete"
				@click="submit"
			/>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Button, Dialog, ErrorMessage, FormControl } from "frappe-ui";
import { Link } from "../../components/Link";
import { IconLabelField } from "../IconPicker";
import { errorMessage } from "../errorMessage";
import type { NavigationItemFormValues, NavigationItemKind } from "./itemKinds";

const props = defineProps<{
	kind: NavigationItemKind;
	onSubmit: (values: NavigationItemFormValues) => Promise<unknown>;
	initial?: NavigationItemFormValues | null;
}>();

const verb = computed(() => (props.initial ? "Edit" : "Add"));

const isOpen = defineModel<boolean>({ default: false });

const target = ref<string | null>("");
const label = ref("");
const icon = ref<string | null>("");
const suggestedLabel = ref("");
const saving = ref(false);
const error = ref("");

const chosenTarget = computed(() => (target.value ?? "").trim());
const isComplete = computed(() => Boolean(chosenTarget.value && label.value.trim()));

function fill() {
	target.value = props.initial?.target ?? "";
	label.value = props.initial?.label ?? "";
	icon.value = props.initial?.icon ?? "";
	suggestedLabel.value = "";
	error.value = "";
}

fill();
watch(isOpen, (open) => open && fill());

watch(target, (value) => {
	error.value = "";
	if (!props.kind.doctype || label.value !== suggestedLabel.value) return;
	label.value = value ?? "";
	suggestedLabel.value = label.value;
});

async function submit() {
	if (!isComplete.value || saving.value) return;

	saving.value = true;
	error.value = "";
	try {
		await props.onSubmit({
			target: chosenTarget.value,
			label: label.value.trim(),
			icon: (icon.value ?? "").trim(),
		});
		isOpen.value = false;
	} catch (exception) {
		error.value = errorMessage(exception);
	} finally {
		saving.value = false;
	}
}
</script>
