<!-- The person's photo, name and email, with a way to upload or remove the photo. -->
<template>
	<div class="flex items-center gap-3 py-1">
		<template v-if="user.loading">
			<Skeleton class="size-11.5 rounded-full" />
			<div class="flex flex-1 flex-col gap-2">
				<Skeleton class="h-4 w-36 rounded-1" />
				<Skeleton class="h-3.5 w-48 rounded-1" />
			</div>
		</template>
		<template v-else>
			<Avatar size="3xl" :image="user.doc.user_image" :label="user.doc.full_name" />
			<div class="min-w-0 flex-1">
				<div class="truncate text-lg font-semibold text-ink-gray-8">
					{{ user.doc.full_name }}
				</div>
				<div class="mt-0.5 truncate text-base text-ink-gray-6">{{ user.doc.email }}</div>
			</div>
			<Button
				v-if="user.doc.user_image"
				:label="__('Remove')"
				variant="ghost"
				:disabled="busy"
				@click="setImage(null)"
			/>
			<Button
				:label="user.doc.user_image ? __('Change photo') : __('Upload photo')"
				:loading="busy"
				@click="uploading = true"
			/>
		</template>
	</div>
	<ErrorMessage v-if="refused" class="pb-1" :message="refused" />
	<FileUploadDialog
		v-if="uploading"
		v-model:open="uploading"
		image-only
		crop
		progress-mode="field"
		:attach-to="{ doctype: 'User', docname: user.doc.name, fieldname: 'user_image' }"
		@uploading="(active: boolean) => (busy = active)"
		@committed="(results: { file_url: string }[]) => results[0] && setImage(results[0].file_url)"
	/>
</template>

<script setup lang="ts">
import { defineAsyncComponent, ref } from "vue";
import { Avatar, Button, ErrorMessage, Skeleton } from "frappe-ui";
import { __ } from "frappe/i18n";

const FileUploadDialog = defineAsyncComponent(
	() => import("@framework/ui/FileUpload/FileUploadDialog.vue")
);

/** The part of the settings dialog's binding this block reads; the full shape is `ComponentBinding`. */
interface Binding {
	readonly doc: Record<string, any>;
	readonly loading: boolean;
	readonly error: string;
	commit(): Promise<void>;
}

const props = defineProps<{ bindings: { user: Binding } }>();
const user = props.bindings.user;

const uploading = ref(false);
const busy = ref(false);
/** The binding's error belongs to the whole draft, so only the one after this block's save shows here. */
const refused = ref("");

async function setImage(url: string | null) {
	uploading.value = false;
	user.doc.user_image = url;
	busy.value = true;
	await user.commit();
	refused.value = user.error;
	busy.value = false;
}
</script>
