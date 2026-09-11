<!-- The `identity` built-in: who this record is. Title, subtitle, image and tags; the tags
     row draws once the record has one, and until then the `tags` quick action adds the first. -->
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

	<!-- The quick actions, when the layout embeds them here. -->
	<slot />

	<div v-if="tags.length" class="flex flex-wrap items-center gap-1.5" data-tags>
		<span
			v-for="tag in tags"
			:key="tag"
			class="group/tag flex items-center gap-1.5 rounded-full border border-outline-gray-2 py-0.5 pl-2 text-sm text-ink-gray-7"
			:class="canWrite ? 'pr-1' : 'pr-2'"
		>
			<span
				class="size-1.5 shrink-0 rounded-full"
				:class="tagColor(tag)"
				aria-hidden="true"
			/>
			{{ tag }}
			<button
				v-if="canWrite"
				type="button"
				class="grid size-4 place-content-center rounded-full text-ink-gray-4 opacity-0 transition hover:bg-surface-gray-3 hover:text-ink-gray-8 focus-visible:opacity-100 group-hover/tag:opacity-100"
				:aria-label="`Remove ${tag}`"
				@click="actions.removeTag(tag)"
			>
				<span class="lucide-x size-3.5" aria-hidden="true" />
			</button>
		</span>

		<TagPicker
			v-if="canWrite"
			:doctype="context.doctype"
			:tags="tags"
			:call="context.controller.page.call"
			@add="actions.addTag"
			@remove="actions.removeTag"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { Avatar } from "frappe-ui";
import { PanelContextKey } from "./context";
import { tagColor, tagsOf } from "./people";
import { peopleActions } from "./peopleActions";
import TagPicker from "./TagPicker.vue";

const context = inject(PanelContextKey)!;
const actions = peopleActions(context);

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

const tags = computed(() => tagsOf(context.docinfo.value));

const canWrite = computed(() => Boolean(context.docinfo.value?.permissions?.write));
</script>
