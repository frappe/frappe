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
	<div
		v-if="session.tags.value.length || session.base.value.length"
		class="flex flex-wrap items-center gap-1.5"
		data-tags
	>
		<template v-for="tag in split.shown" :key="tag">
			<!-- Stopped, or the open picker's outside-press closes it before this click moves it. -->
			<button
				v-if="canWrite"
				type="button"
				class="min-w-0 rounded-full focus-visible:outline-none focus-visible:ring focus-visible:ring-outline-gray-3"
				aria-haspopup="listbox"
				:data-tag-chip="tag"
				@pointerdown.stop
				@click="picker?.openOn(tag)"
			>
				<TagChip :tag="tag" />
			</button>
			<TagChip v-else :tag="tag" />
		</template>

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

		<TagPicker
			v-if="canWrite"
			ref="picker"
			shortcut
			side="bottom"
			align="end"
			:session="session"
		>
			<template #trigger>
				<!-- The trigger must own a box: Tooltip drops the attrs the popover anchors on. -->
				<div class="flex shrink-0">
					<Tooltip :text="__('Add')">
						<button
							type="button"
							class="grid size-6 place-content-center rounded-full text-ink-gray-5 transition hover:bg-surface-gray-2 hover:text-ink-gray-7"
							aria-label="Add tag"
							data-add-tag
						>
							<span class="lucide-plus size-3.5" aria-hidden="true" />
						</button>
					</Tooltip>
				</div>
			</template>
		</TagPicker>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, useTemplateRef } from "vue";
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

const picker = useTemplateRef<InstanceType<typeof TagPicker>>("picker");

const canWrite = computed(() => Boolean(context.docinfo.value?.permissions?.write));
</script>
