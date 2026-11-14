<!-- "Fetch a field…" on a Link field: FetchMenu on the linked DocType's fields; the pick adds a
     read-only field after the Link. The canvas "⋯" menu opens it through `fetchAsked`. -->
<template>
	<Popover v-model:open="open" side="bottom" align="end">
		<template #trigger>
			<button
				type="button"
				class="flex h-7 w-full min-w-0 items-center gap-2 rounded-4 px-2 text-left text-base text-ink-gray-8"
				:class="open ? 'bg-surface-gray-3' : 'hover:bg-surface-gray-2'"
				data-fetch-add
			>
				<span class="lucide-plus size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
				<span class="min-w-0 truncate">{{ __("Fetch a field…") }}</span>
			</button>
		</template>
		<FetchMenu :links="[link]" :link="link" @pick="pick" @close="open = false" />
	</Popover>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { Popover } from "frappe-ui";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { fetchAsked } from "./fetchFrom";
import FetchMenu from "./FetchMenu.vue";

const props = defineProps<{ link: RawMetaField }>();

const open = ref(false);

watch(
	fetchAsked,
	(asked) => {
		if (asked !== props.link.fieldname) return;
		fetchAsked.value = null;
		open.value = true;
	},
	{ immediate: true }
);

function pick(link: RawMetaField, source: RawMetaField) {
	open.value = false;
	const { fieldname, label, fieldtype, options } = source;
	void acts.perform("fields.fetch_field", {
		link: link.fieldname,
		source: { fieldname, label, fieldtype, options },
	});
}
</script>
