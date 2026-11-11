<!-- The Tags column: `_user_tags` is a comma string, with a leading comma when set. -->
<template>
	<div class="flex min-w-0 items-center gap-1">
		<div class="flex min-w-0 items-center gap-1 overflow-hidden">
			<TagChip v-for="tag in visible" :key="tag" :tag="tag" class="min-w-16 shrink" />
		</div>
		<Tooltip v-if="hidden.length" :text="hidden.join(', ')">
			<span class="shrink-0 text-sm text-ink-gray-6" data-more-tags>
				{{ __("+{0} more", [String(hidden.length)]) }}
			</span>
		</Tooltip>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Tooltip } from "frappe-ui";
import { __ } from "@/i18n";
import TagChip from "../record/panel/TagChip.vue";

const props = defineProps<{ value: unknown }>();

// Collapse only past VISIBLE + 1, so "+1 more" never stands in for the one tag it hides.
const VISIBLE = 3;

const tags = computed(() =>
	typeof props.value === "string" ? props.value.split(",").filter(Boolean) : []
);
const visible = computed(() =>
	tags.value.length > VISIBLE + 1 ? tags.value.slice(0, VISIBLE) : tags.value
);
const hidden = computed(() => tags.value.slice(visible.value.length));
</script>
