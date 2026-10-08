<template>
	<span class="inline-flex max-w-full">
		<!-- previewable (image/text) opens a dialog; else a plain download link -->
		<component :is="wrapper.tag" v-bind="wrapper.attrs" class="inline-flex max-w-full">
			<Button
				class="group max-w-full"
				:label="label"
				theme="gray"
				variant="outline"
				@click="openPreview"
			>
				<template #prefix>
					<LucidePaperclip
						class="h-4 w-4"
						:class="preview && url && 'group-hover:hidden'"
					/>
					<a
						v-if="preview && url"
						:href="url"
						:download="label"
						class="hidden text-ink-gray-5 hover:text-ink-gray-8 group-hover:grid"
						@click.stop
					>
						<LucideDownload class="h-4 w-4" />
					</a>
				</template>
				<template #suffix>
					<slot name="suffix" />
				</template>
			</Button>
		</component>

		<Dialog v-if="preview && url" v-model:open="previewOpen" :title="label" size="4xl">
			<template #default>
				<div v-if="error" class="text-sm text-ink-red-6">
					Couldn't load this file: {{ error }}
				</div>
				<div
					v-else-if="preview === 'text'"
					class="prose prose-sm max-w-none whitespace-pre-wrap"
				>
					{{ textContent }}
				</div>
				<img v-else-if="preview === 'image'" :src="url" class="m-auto rounded border" />
				<video
					v-else-if="preview === 'video'"
					:src="url"
					controls
					class="m-auto max-h-[70vh] rounded border"
				/>
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
const VIDEO_EXTS = new Set(["mp4", "mov", "webm", "mkv", "avi", "m4v"]);

// only images, text files, and video preview in a dialog; everything else downloads
const preview = computed<"image" | "text" | "video" | null>(() => {
	if (!props.url) return null;
	const ext = (props.label.split(".").pop() || "").toLowerCase();
	if (IMAGE_EXTS.has(ext)) return "image";
	if (TEXT_EXTS.has(ext)) return "text";
	if (VIDEO_EXTS.has(ext)) return "video";
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
const error = ref<string | null>(null);

// fetch text lazily on first open
watch(previewOpen, async (isOpen) => {
	if (isOpen && preview.value === "text" && props.url && !textContent.value) {
		error.value = null;
		try {
			const res = await fetch(props.url);
			if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
			textContent.value = await res.text();
		} catch (e) {
			error.value = e instanceof Error ? e.message : "Failed to load file";
		}
	}
});
</script>
