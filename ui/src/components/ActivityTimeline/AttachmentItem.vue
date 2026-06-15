<template>
	<span>
		<a :href="preview ? undefined : url || undefined" target="_blank">
			<Button
				:label="label"
				theme="gray"
				variant="outline"
				@click="preview && (showDialog = true)"
			>
				<template #prefix>
					<FeatherIcon :name="iconName" class="h-4 w-4" />
				</template>
				<template #suffix>
					<slot name="suffix" />
				</template>
			</Button>
		</a>
		<PreviewDialog
			v-if="preview && url"
			v-model="showDialog"
			:label="label"
			:url="url"
			:type="preview"
		/>
	</span>
</template>

<script setup lang="ts">
import { Button, FeatherIcon } from "frappe-ui";
import { computed, ref } from "vue";
import PreviewDialog from "./PreviewDialog.vue";

const props = withDefaults(
	defineProps<{
		label: string;
		url?: string | null;
	}>(),
	{
		url: null,
	}
);

type AttachmentKind = "image" | "video" | "pdf" | "spreadsheet" | "text" | "file";

const KIND_BY_EXT: Record<string, AttachmentKind> = {
	png: "image",
	jpg: "image",
	jpeg: "image",
	gif: "image",
	webp: "image",
	svg: "image",
	bmp: "image",
	mp4: "video",
	webm: "video",
	mov: "video",
	avi: "video",
	pdf: "pdf",
	xls: "spreadsheet",
	xlsx: "spreadsheet",
	csv: "spreadsheet",
	ods: "spreadsheet",
	txt: "text",
	md: "text",
	log: "text",
};

// Feather icon shown on the attachment button for each kind of file
const ICON_MAP: Record<AttachmentKind, string> = {
	image: "image",
	video: "video",
	pdf: "file-text",
	spreadsheet: "grid",
	text: "file-text",
	file: "file",
};

function getKind(label: string): AttachmentKind {
	const ext = (label.split(".").pop() || "").toLowerCase();
	return KIND_BY_EXT[ext] || "file";
}

const kind = computed(() => getKind(props.label));
const iconName = computed(() => ICON_MAP[kind.value]);

// What the dialog can render for this file, if anything
const preview = computed<"image" | "text" | null>(() => {
	if (!props.url) return null;
	return kind.value === "image" || kind.value === "text" ? kind.value : null;
});

const showDialog = ref(false);
</script>
