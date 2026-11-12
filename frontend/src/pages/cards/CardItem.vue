<!-- One card: the title and the clipped body over a footer with the owner and the last change. -->
<template>
	<RouterLink
		:to="link"
		class="group relative flex h-56 min-w-0 flex-col gap-2 overflow-hidden rounded-5 border bg-surface-base p-3"
		:class="
			selected
				? 'border-outline-gray-5 ring-1 ring-outline-gray-5'
				: 'border-outline-gray-2 hover:border-outline-gray-3'
		"
	>
		<div
			class="truncate text-base"
			:class="[titleClass || 'font-medium text-ink-gray-9', selecting && 'pe-8']"
		>
			{{ title }}
		</div>
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
		<!-- Beside the menu on hover; on every card once one is selected, when the menu is gone. -->
		<div
			role="checkbox"
			:aria-checked="!!selected"
			:aria-label="__('Select {0}', [row.name])"
			tabindex="0"
			class="absolute top-2 flex size-7 items-center justify-center rounded-3 [&_input]:mt-0"
			:class="
				selecting
					? 'end-2 opacity-100'
					: [
							menu.length ? 'end-9' : 'end-2',
							'opacity-0 focus:opacity-100 group-hover:opacity-100',
					  ]
			"
			@click.stop.prevent="emit('toggle')"
			@keydown.enter.stop.prevent="emit('toggle')"
			@keydown.space.stop.prevent="emit('toggle')"
		>
			<Checkbox
				:modelValue="selected"
				class="pointer-events-none"
				tabindex="-1"
				aria-hidden="true"
			/>
		</div>
		<div
			v-if="menu.length && !selecting"
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
import { Checkbox } from "frappe-ui";
import { computed } from "vue";
import type { RouteLocationRaw } from "vue-router";
import FieldCell from "@/pages/list/FieldCell.vue";
import RowMenu from "@/pages/list/RowMenu.vue";
import type { RowMenuOption } from "@/pages/list/rowActions";
import { __ } from "@/i18n";
import type { Person } from "./useCardsView";
import type { ListMeta } from "@/list/defaults";
import { recordTitle } from "@/recordTitle";

// The footer's time is the list cell's: the same relative text, the exact date on hover.
const MODIFIED = {
	fieldname: "modified",
	fieldtype: "Datetime",
	label: "Last Modified",
} as FieldMeta;

const props = defineProps<{
	row: Record<string, unknown>;
	meta: ListMeta | null;
	titleField: string;
	bodyField: string | null;
	bodyIsHtml: boolean;
	link: RouteLocationRaw;
	/** The title's seen look on a Track Seen doctype; empty keeps the default. */
	titleClass?: string;
	menu: RowMenuOption[];
	person?: Person;
	selected?: boolean;
	/** Any card is selected: every card shows its checkbox and none its menu. */
	selecting?: boolean;
}>();

const emit = defineEmits<{ toggle: [] }>();

const title = computed(() =>
	recordTitle(props.meta, props.row, String(props.row.name), props.titleField)
);
const body = computed(() => (props.bodyField ? String(props.row[props.bodyField] ?? "") : ""));
const owner = computed(() => props.person?.name || String(props.row.owner ?? ""));
const image = computed(() => props.person?.image ?? null);
</script>
