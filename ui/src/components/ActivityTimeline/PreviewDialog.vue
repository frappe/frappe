<template>
	<Dialog v-model:open="open" :title="label" size="4xl">
		<template #default>
			<div v-if="type === 'text'" class="prose prose-sm max-w-none whitespace-pre-wrap">
				{{ content }}
			</div>
			<img v-else-if="type === 'image'" :src="url" class="m-auto rounded border" />
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Dialog } from "frappe-ui";
import { ref, watch } from "vue";

const props = defineProps<{
	label: string;
	url: string;
	type: "image" | "text";
}>();

const open = defineModel<boolean>({ default: false });

const content = ref("");

// fetch text lazily on first open, then cache
watch(open, async (isOpen) => {
	if (isOpen && props.type === "text" && !content.value) {
		content.value = await fetch(props.url).then((res) => res.text());
	}
});
</script>
