<!-- The Fetch from control: "Customer › Customer Name", or "None". A click opens FetchMenu below
     it, right edges together. A value that names no Link field shows as code and keeps its text. -->
<template>
	<Popover v-model:open="open" side="bottom" align="end">
		<template #trigger>
			<button
				type="button"
				class="flex h-7 w-full min-w-0 items-center gap-1.5 rounded-4 px-2 text-left text-base"
				:class="open ? 'bg-surface-gray-3' : 'hover:bg-surface-gray-2'"
				:title="words"
				data-fetch-row
			>
				<span v-if="!value" class="min-w-0 flex-1 truncate text-ink-gray-5">{{
					__("None")
				}}</span>
				<span
					v-else-if="!link"
					class="min-w-0 flex-1 truncate font-mono text-sm text-ink-gray-7"
				>
					{{ value }}
				</span>
				<span v-else class="flex min-w-0 flex-1 items-center gap-1 text-ink-gray-8">
					<span class="shrink-0">{{ linkLabel }}</span>
					<span class="shrink-0 text-ink-gray-4">›</span>
					<span class="min-w-0 truncate">{{ sourceLabel }}</span>
				</span>
				<span
					class="lucide-chevron-down size-4 shrink-0 text-ink-gray-5"
					aria-hidden="true"
				/>
			</button>
		</template>
		<FetchMenu :links="links" :value="value" @pick="pick" @close="open = false" />
		<div v-if="value" class="border-t border-outline-gray-1 p-1.5">
			<button
				type="button"
				class="flex h-7 w-full items-center gap-2 rounded-4 px-2 text-left text-base text-ink-gray-7 hover:bg-surface-gray-3"
				data-fetch-clear
				@click="clear"
			>
				<span class="lucide-x size-4 text-ink-gray-5" aria-hidden="true" />
				{{ __("Stop fetching") }}
			</button>
		</div>
	</Popover>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Popover } from "frappe-ui";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { fetchFromText, linkFields, parseFetchFrom } from "./fetchFrom";
import FetchMenu from "./FetchMenu.vue";

const props = defineProps<{ canvas: DesignCanvas; field: RawMetaField }>();

const open = ref(false);
const value = computed(() => props.field.fetch_from ?? "");
const links = computed(() => linkFields(props.canvas.working.value.fields, props.field.fieldname));
const path = computed(() => parseFetchFrom(value.value));
const link = computed(() => links.value.find((one) => one.fieldname === path.value?.link));
const { meta } = useDoctypeMeta(() => link.value?.options ?? "");
const linkLabel = computed(() => link.value?.label || link.value?.fieldname);
const sourceLabel = computed(() => {
	const source = path.value?.source;
	return meta.value?.fields?.find((one) => one.fieldname === source)?.label || source;
});
const words = computed(() =>
	link.value ? `${linkLabel.value} › ${sourceLabel.value}` : value.value
);

function pick(one: RawMetaField, source: RawMetaField) {
	open.value = false;
	set({ fetch_from: fetchFromText({ link: one.fieldname, source: source.fieldname }) });
}

function clear() {
	open.value = false;
	set({ fetch_from: "", ...(props.field.fetch_if_empty ? { fetch_if_empty: 0 } : {}) });
}

function set(properties: Record<string, unknown>) {
	if (properties.fetch_from === value.value) return;
	void acts.perform("fields.set_field_property", {
		fieldname: props.field.fieldname,
		properties,
	});
}
</script>
