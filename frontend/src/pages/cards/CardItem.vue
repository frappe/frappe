<!-- One card: the title and the clipped body over a footer with the owner and the last change. -->
<template>
	<RouterLink
		:to="link"
		class="group relative flex h-56 min-w-0 flex-col gap-2 overflow-hidden rounded-5 border border-outline-gray-2 bg-surface-base p-3 hover:border-outline-gray-3"
	>
		<div class="truncate text-base font-medium text-ink-gray-9">{{ title }}</div>
		<div
			class="pointer-events-none relative min-h-0 flex-1 overflow-hidden text-p-sm text-ink-gray-7"
		>
			<RichTextView v-if="bodyIsHtml" :html="body" />
			<div v-else class="whitespace-pre-line">{{ body }}</div>
			<div
				class="absolute inset-x-0 bottom-0 h-6 bg-gradient-to-t from-surface-base to-transparent"
			/>
		</div>
		<div class="flex min-w-0 items-center gap-2 text-sm text-ink-gray-5">
			<template v-if="owner">
				<LinkMark
					:source="{ kind: 'image', field: 'user_image' }"
					:value="image"
					:text="owner"
				/>
				<span class="truncate">{{ owner }}</span>
			</template>
			<span class="ms-auto shrink-0">
				<FieldCell :field="MODIFIED" :row="row" />
			</span>
		</div>
		<div
			v-if="menu.length"
			class="absolute end-2 top-2 opacity-0 focus-within:opacity-100 group-hover:opacity-100 has-[[data-state=open]]:opacity-100"
			@click.prevent.stop
		>
			<RowMenu :options="menu" />
		</div>
	</RouterLink>
</template>

<script setup lang="ts">
import { LinkMark } from "@framework/ui/fields";
import type { FieldMeta } from "@framework/ui/fields/types";
import { RichTextView } from "@framework/ui/RichText";
import { computed } from "vue";
import type { RouteLocationRaw } from "vue-router";
import FieldCell from "@/pages/list/FieldCell.vue";
import RowMenu from "@/pages/list/RowMenu.vue";
import type { RowMenuOption } from "@/pages/list/rowActions";
import type { Person } from "./useCardsView";

// The footer's time is the list cell's: the same relative text, the exact date on hover.
const MODIFIED = {
	fieldname: "modified",
	fieldtype: "Datetime",
	label: "Last Modified",
} as FieldMeta;

const props = defineProps<{
	row: Record<string, unknown>;
	titleField: string;
	bodyField: string | null;
	bodyIsHtml: boolean;
	link: RouteLocationRaw;
	menu: RowMenuOption[];
	person?: Person;
}>();

const title = computed(() => String(props.row[props.titleField] || props.row.name));
const body = computed(() => (props.bodyField ? String(props.row[props.bodyField] ?? "") : ""));
const owner = computed(() => props.person?.name || String(props.row.owner ?? ""));
const image = computed(() => props.person?.image ?? null);
</script>
