<!-- The `identity` built-in: who this record is. Title, subtitle, image and tags; the tags
     row draws only once the record has one. -->
<template>
	<div class="flex items-start gap-3">
		<Avatar
			v-if="image"
			:image="image"
			:label="title"
			shape="square"
			class="size-16 shrink-0"
		/>
		<div class="min-w-0 flex-1">
			<p class="truncate text-lg font-semibold text-ink-gray-9">{{ title }}</p>
			<p class="mt-0.5 truncate text-sm text-ink-gray-5">{{ subtitle }}</p>
		</div>
	</div>

	<div v-if="tags.length" class="flex flex-wrap items-center gap-1.5" data-tags>
		<span
			v-for="tag in tags"
			:key="tag"
			class="rounded-full border border-outline-gray-2 px-2 py-0.5 text-sm text-ink-gray-7"
		>
			{{ tag }}
		</span>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Avatar } from "frappe-ui";
import { PanelContextKey } from "./context";

const context = inject(PanelContextKey)!;

const title = computed(() => {
	const field = context.meta.value?.title_field;
	return String((field && context.doc.value[field]) || context.docname);
});

// The name where the title is something else; the doctype where the name is the title.
const subtitle = computed(() =>
	title.value === context.docname ? context.doctype : context.docname
);

const image = computed(() => {
	const field = context.meta.value?.image_field;
	return field ? (context.doc.value[field] as string | undefined) : undefined;
});

const tags = computed(() =>
	(context.docinfo.value?.tags ?? "")
		.split(",")
		.map((tag) => tag.trim())
		.filter(Boolean)
);
</script>
