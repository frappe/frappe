<template>
	<form class="flex flex-col gap-4" @submit.prevent="submit">
		<div class="flex flex-col gap-1.5">
			<span class="text-xs text-ink-gray-5">{{ text.logoLabel }}</span>
			<div class="flex items-center gap-2">
				<span
					class="flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-4 bg-surface-gray-2 text-base font-medium text-ink-gray-7"
				>
					<img
						v-if="logo"
						:src="logo"
						:alt="text.logoLabel"
						class="size-full object-cover"
					/>
					<slot v-else name="placeholder">
						<span aria-hidden="true">{{ initial }}</span>
					</slot>
				</span>
				<Button
					variant="subtle"
					icon-left="lucide-upload"
					:label="logo ? text.reupload : text.upload"
					:loading="logoUpload.isUploading.value"
					@click="picker?.click()"
				/>
				<Button v-if="logo" variant="ghost" :label="text.remove" @click="logo = ''" />
				<input ref="picker" type="file" accept="image/*" class="hidden" @change="pick" />
			</div>
		</div>
		<FormControl
			v-model="name"
			variant="outline"
			size="md"
			:label="text.nameLabel"
			:placeholder="text.namePlaceholder"
			:maxlength="maxLength"
			required
			autofocus
		/>
		<slot />
		<Button
			type="submit"
			variant="solid"
			class="self-end"
			:label="text.save"
			:loading="saving"
			:disabled="!name.trim() || logoUpload.isUploading.value"
		/>
		<ErrorMessage :message="error" />
	</form>
</template>

<script setup lang="ts">
import { useEventListener } from "@vueuse/core";
import { Button, ErrorMessage, FormControl, useFileUpload } from "frappe-ui";
import { computed, onActivated, onDeactivated, ref } from "vue";

/** English defaults; pass translated text to relabel. */
export interface BrandStepLabels {
	logoLabel: string;
	upload: string;
	reupload: string;
	remove: string;
	nameLabel: string;
	namePlaceholder: string;
	save: string;
	notAnImage: string;
	uploadFailed: string;
	failed: string;
}

const props = defineProps<{
	/** Stores the name and logo where the app keeps its brand. The step moves on once it resolves. */
	save: (brand: { name: string; logo: string }) => Promise<unknown>;
	labels?: Partial<BrandStepLabels>;
	maxLength?: number;
}>();
const emit = defineEmits<{ done: [] }>();
const name = defineModel<string>("name", { default: "" });
const logo = defineModel<string>("logo", { default: "" });

const defaults: BrandStepLabels = {
	logoLabel: "Logo",
	upload: "Upload",
	reupload: "Reupload",
	remove: "Remove",
	nameLabel: "Name",
	namePlaceholder: "Acme",
	save: "Continue",
	notAnImage: "Choose an image file.",
	uploadFailed: "That logo could not be uploaded. Try another.",
	failed: "That could not be saved. Try again.",
};
const text = computed(() => ({ ...defaults, ...props.labels }));
const initial = computed(() => (name.value.trim()[0] || "A").toUpperCase());

const picker = ref<HTMLInputElement | null>(null);
const logoUpload = useFileUpload();
const error = ref("");

function pick(event: Event) {
	const input = event.target as HTMLInputElement;
	upload(input.files?.[0]);
	input.value = "";
}

// A logo copied to the clipboard can be pasted anywhere on the step, while it is on screen:
// a host that keeps steps alive must not upload a logo pasted on another step.
const onScreen = ref(true);
onActivated(() => (onScreen.value = true));
onDeactivated(() => (onScreen.value = false));
useEventListener(document, "paste", (event: ClipboardEvent) => {
	if (!onScreen.value) return;
	const file = Array.from(event.clipboardData?.files ?? []).find((f) =>
		f.type.startsWith("image/")
	);
	if (!file) return;
	event.preventDefault();
	upload(file);
});

async function upload(file?: File) {
	if (!file) return;
	error.value = "";
	if (!file.type.startsWith("image/")) {
		error.value = text.value.notAnImage;
		return;
	}
	try {
		const uploaded = await logoUpload.upload(file, { private: false });
		logo.value = uploaded.file_url;
	} catch (e: unknown) {
		error.value = (e as { message?: string })?.message || text.value.uploadFailed;
	}
}

const saving = ref(false);

async function submit() {
	if (!name.value.trim() || saving.value) return;
	saving.value = true;
	error.value = "";
	try {
		await props.save({ name: name.value.trim(), logo: logo.value });
		emit("done");
	} catch (e: unknown) {
		error.value = (e as { messages?: string[] })?.messages?.join(" ") || text.value.failed;
	} finally {
		saving.value = false;
	}
}
</script>
