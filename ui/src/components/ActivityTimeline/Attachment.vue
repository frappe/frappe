<template>
	<span>
		<!-- previewable (image/text) opens a dialog; else a plain download link -->
		<component :is="wrapper.tag" v-bind="wrapper.attrs">
			<Button :label="label" theme="gray" variant="outline" @click="openPreview">
				<template #prefix>
					<LucidePaperclip class="h-4 w-4" />
				</template>
				<template #suffix>
					<slot name="suffix" />
				</template>
			</Button>
		</component>

		<Dialog v-if="preview && url" v-model:open="previewOpen" :title="label" size="4xl">
			<template #default>
				<div
					v-if="preview === 'text'"
					class="prose prose-sm max-w-none whitespace-pre-wrap"
				>
					{{ textContent }}
				</div>
				<img v-else-if="preview === 'image'" :src="url" class="m-auto rounded border" />
			</template>
		</Dialog>
	</span>
</template>

<script setup lang="ts">
import { Button, Dialog } from "frappe-ui";
import { computed, ref, watch } from "vue";

const props = withDefaults(
	defineProps<{
		label: string;
		url?: string | null;
	}>(),
	{
		url: null,
	}
);

const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"]);
const TEXT_EXTS = new Set(["txt", "md", "log"]);

// only images and text files preview in a dialog; everything else downloads
const preview = computed<"image" | "text" | null>(() => {
	if (!props.url) return null;
	const ext = (props.label.split(".").pop() || "").toLowerCase();
	if (IMAGE_EXTS.has(ext)) return "image";
	if (TEXT_EXTS.has(ext)) return "text";
	return null;
});

// previewable triggers the dialog; else a real download/navigate link
const wrapper = computed(() =>
	preview.value
		? { tag: "span", attrs: {} }
		: { tag: "a", attrs: { href: props.url || undefined, target: "_blank" } }
);

const previewOpen = ref(false);
function openPreview() {
	if (preview.value) previewOpen.value = true;
}

const textContent = ref("");

// fetch text lazily on first open
watch(previewOpen, async (isOpen) => {
	if (isOpen && preview.value === "text" && props.url && !textContent.value) {
		textContent.value = await fetch(props.url).then((res) => res.text());
	}
});
</script>
