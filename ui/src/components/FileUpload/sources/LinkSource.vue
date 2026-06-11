<template>
	<div class="flex min-h-64 flex-col justify-center gap-3">
		<TextInput
			v-model="url"
			type="url"
			placeholder="https://example.com/file.pdf"
			@keydown.enter.prevent="addLink"
		>
			<template #prefix>
				<span class="lucide-link size-3.5 text-ink-gray-5" aria-hidden="true" />
			</template>
		</TextInput>
		<div class="flex justify-end">
			<Button variant="solid" label="Add link" :disabled="!url.trim()" @click="addLink" />
		</div>
	</div>
</template>

<script setup lang="ts">
// Link source: a single URL is stored directly as an attachment — no upload, no
// POST. Emits the trimmed URL via `link`; the dialog enqueues it through the
// uploader's `addLink`, which commits it verbatim.
import { ref } from "vue";
import { Button, TextInput } from "frappe-ui";

const emit = defineEmits<{ link: [string] }>();

const url = ref("");

// Dangerous protocols that become a clickable XSS vector once rendered as an
// `<a href>`. Authoritative validation lives in the uploader's `addLink`; this
// lightweight check just avoids emitting obvious junk.
const unsafeProtocols = ["javascript:", "data:", "vbscript:"];

function addLink() {
	const trimmed = url.value.trim();
	if (!trimmed) return;
	const lower = trimmed.toLowerCase();
	if (unsafeProtocols.some((p) => lower.startsWith(p))) return;
	emit("link", trimmed);
	url.value = "";
}
</script>
