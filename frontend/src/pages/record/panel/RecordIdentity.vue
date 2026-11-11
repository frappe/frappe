<!-- The `identity` built-in: who this record is. Title, subtitle, image and tags; the tags
     row draws once the record has one, and until then the `tags` quick action adds the first. -->
<template>
	<div class="flex items-start gap-3">
		<RecordImage v-if="hasImage" :label="title" />
		<!-- Beside the tile the column spans its height, so the actions sit level with its foot. -->
		<div
			class="flex min-w-0 flex-1 flex-col"
			:class="hasImage ? 'h-20 justify-between' : 'gap-2.5'"
		>
			<div class="min-w-0">
				<p class="truncate text-lg font-semibold text-ink-gray-9">{{ title }}</p>
				<p class="mt-0.5 truncate text-sm text-ink-gray-5">{{ subtitle }}</p>
			</div>

			<!-- The quick actions, when the layout embeds them here. -->
			<slot />
		</div>
	</div>

	<div v-if="tags.length" class="flex flex-wrap items-center gap-1.5" data-tags>
		<TagChip v-for="tag in tags" :key="tag" :tag="tag" :class="{ 'pr-1': canWrite }">
			<button
				v-if="canWrite"
				type="button"
				class="grid size-4 place-content-center rounded-full text-ink-gray-4 opacity-0 transition hover:bg-surface-gray-3 hover:text-ink-gray-8 focus-visible:opacity-100 group-hover/tag:opacity-100"
				:aria-label="`Remove ${tag}`"
				@click="actions.removeTag(tag)"
			>
				<span class="lucide-x size-3.5" aria-hidden="true" />
			</button>
		</TagChip>

		<TagPicker
			v-if="canWrite"
			:tags="tags"
			@add="actions.addTag"
			@remove="actions.removeTag"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { PanelContextKey } from "./context";
import { tagsOf } from "./people";
import TagChip from "./TagChip.vue";
import { peopleActions } from "./peopleActions";
import RecordImage from "./RecordImage.vue";
import TagPicker from "./TagPicker.vue";
import { recordTitle } from "@/recordTitle";

const context = inject(PanelContextKey)!;
const actions = peopleActions(context);

const title = computed(() => recordTitle(context.meta.value, context.doc.value, context.docname));

// The name where the title is something else; the doctype where the name is the title.
const subtitle = computed(() =>
	title.value === context.docname ? context.doctype : context.docname
);

const hasImage = computed(() => Boolean(context.meta.value?.image_field));

const tags = computed(() => tagsOf(context.docinfo.value));

const canWrite = computed(() => Boolean(context.docinfo.value?.permissions?.write));
</script>
