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

	<!-- `base` keeps the row while its picker unticks the last tag, or it would unmount mid-session. -->
	<div v-if="session.tags.value.length || session.base.value.length" class="relative">
		<!-- Anchored on the whole row, so both popovers open beside the chips, never over them. -->
		<TagPicker v-if="canWrite" v-model:open="picking" anchored shortcut :session="session" />
		<div class="flex flex-wrap items-center gap-1.5" data-tags>
			<TagChip v-for="tag in split.shown" :key="tag" :tag="tag" :class="{ 'pr-1': canWrite }">
				<button
					v-if="canWrite"
					type="button"
					class="grid size-4 place-content-center rounded-full text-ink-gray-4 opacity-0 transition hover:bg-surface-gray-3 hover:text-ink-gray-8 focus-visible:opacity-100 group-hover/tag:opacity-100"
					:aria-label="`Remove ${tag}`"
					@click="session.remove(tag)"
				>
					<span class="lucide-x size-3.5" aria-hidden="true" />
				</button>
			</TagChip>

			<Tooltip v-if="split.hidden.length" :text="split.hidden.join(', ')">
				<Badge
					theme="gray"
					variant="outline"
					size="lg"
					class="shrink-0 text-ink-gray-7"
					data-more-tags
				>
					{{ __("+{0} more", [split.hidden.length]) }}
				</Badge>
			</Tooltip>

			<Tooltip v-if="canWrite" :text="__('Add')">
				<!-- Stopped, or the picker's outside-press closes it and this click opens it again. -->
				<button
					type="button"
					class="grid size-6 place-content-center rounded-full text-ink-gray-5 transition hover:bg-surface-gray-2 hover:text-ink-gray-7"
					aria-label="Add tag"
					data-add-tag
					@pointerdown.stop
					@click="picking = !picking"
				>
					<span class="lucide-plus size-3.5" aria-hidden="true" />
				</button>
			</Tooltip>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, ref } from "vue";
import { PanelContextKey } from "./context";
import { splitTags } from "./tagSession";
import TagChip from "./TagChip.vue";
import { peopleActions } from "./peopleActions";
import RecordImage from "./RecordImage.vue";
import TagPicker from "./TagPicker.vue";
import { Badge, Tooltip } from "frappe-ui";
import { __ } from "@/i18n";
import { recordTitle } from "@/recordTitle";

const context = inject(PanelContextKey)!;
const actions = peopleActions(context);

const title = computed(() => recordTitle(context.meta.value, context.doc.value, context.docname));

// The name where the title is something else; the doctype where the name is the title.
const subtitle = computed(() =>
	title.value === context.docname ? context.doctype : context.docname
);

const hasImage = computed(() => Boolean(context.meta.value?.image_field));

const session = actions.tagSession;
const split = computed(() => splitTags(session.tags.value));

const picking = ref(false);

const canWrite = computed(() => Boolean(context.docinfo.value?.permissions?.write));
</script>
