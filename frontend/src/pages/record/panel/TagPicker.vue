<!-- A tag picker with a create row: a pick adds, an unpick removes. The trigger is the caller's,
     or a bare anchor over whatever opens it. -->
<template>
	<TagColorPopover
		:open="Boolean(pending)"
		:tag="pending"
		:current="recolouring ? tagColorName(recolouring) : undefined"
		:side="side"
		:align="align"
		@select="pickColor"
		@close="pickColor()"
	>
		<!-- Bound only when something else opens it: an undefined boolean prop reads as false. -->
		<MultiSelect
			v-bind="anchored || shortcut ? { open } : {}"
			:modelValue="session.tags.value"
			v-model:query="query"
			:options="options"
			:loading="loading"
			:filterable="false"
			:placeholder="__('Search or create tags')"
			:side="side"
			:align="align"
			@update:modelValue="onPick"
			@update:query="searchSoon"
			@update:open="(opened: boolean) => (open = opened)"
			@highlight="onHighlight"
		>
			<template #trigger>
				<!-- It only positions the popover; taking clicks would swallow the trigger it covers. -->
				<div
					v-if="anchored"
					class="pointer-events-none absolute inset-0"
					aria-hidden="true"
				/>
				<slot v-else name="trigger" />
			</template>

			<template #search-suffix>
				<KeyboardShortcut v-if="shortcut && !query" combo="G" class="leading-none" />
			</template>

			<template #item-prefix="{ item }">
				<button
					type="button"
					tabindex="-1"
					class="grid size-4 shrink-0 place-content-center rounded-full hover:bg-surface-gray-3"
					:aria-label="__('Change color of {0}', [item.label])"
					:data-recolour="item.value"
					@pointerdown.stop.prevent
					@click.stop.prevent="startRecolour(String(item.value))"
				>
					<span
						class="size-2 rounded-full"
						:class="tagColorClass(String(item.value))"
						aria-hidden="true"
					/>
				</button>
			</template>

			<template #empty>
				<span class="text-p-sm">{{ error || __("No tags yet, type to create one") }}</span>
			</template>

			<!-- Marks this picker's popover for the unscoped CSS below; it is portaled out. -->
			<template #footer
				><span class="tag-picker-marker hidden" aria-hidden="true"
			/></template>
		</MultiSelect>
	</TagColorPopover>
</template>

<script setup lang="ts">
import { computed, h, onBeforeUnmount, ref, watch } from "vue";
import { useEventListener } from "@vueuse/core";
import { KeyboardShortcut, MultiSelect, useKeyboardShortcut } from "frappe-ui";
import { canCreateTag, matchingTags } from "./people";
import { useTagSearch, type SearchOption } from "./remoteSearch";
import TagColorPopover from "./TagColorPopover.vue";
import { appliedFirst, type TagSession } from "./tagSession";
import { __ } from "@/i18n";
import { tagColorClass, tagColorName } from "@/tagColors";

const props = withDefaults(
	defineProps<{
		session: TagSession;
		/** Overlays whatever it sits on and opens from `open` alone. */
		anchored?: boolean;
		/** Binds G to open the picker. */
		shortcut?: boolean;
		side?: "top" | "right" | "bottom" | "left";
		align?: "start" | "center" | "end";
	}>(),
	{ side: "left", align: "start" }
);

// Left undefined, the picker owns its open state.
const open = defineModel<boolean | undefined>("open", { default: undefined });

const CREATE_VALUE = "__create__";

const query = ref("");
const naming = ref("");
const recolouring = ref("");
const pending = computed(() => naming.value || recolouring.value);
const target = ref("");

// The record's own tags fill a paged answer's gaps, so one already on it is never offered as new.
const pinned = computed<SearchOption[]>(() =>
	matchingTags(props.session.listed.value, query.value).map((tag) => ({
		label: tag,
		value: tag,
	}))
);
const { options: found, loading, error, search, searchSoon } = useTagSearch(pinned);

const canCreate = computed(() =>
	canCreateTag(
		found.value.map((option) => option.value),
		query.value
	)
);

// Sorted by the opening snapshot, so a tick never moves a row under the pointer.
const options = computed<Record<string, unknown>[]>(() => {
	const rows: Record<string, unknown>[] = appliedFirst(found.value, props.session.base.value);
	if (canCreate.value) rows.push(createRow(query.value.trim()));
	return rows;
});

function createRow(text: string) {
	const row = () =>
		h(
			"span",
			{
				class: "flex min-h-7 w-full min-w-0 items-center gap-2 px-2 py-1.5 text-base text-ink-gray-7",
			},
			[
				h("span", {
					class: "lucide-plus size-3.5 shrink-0 text-ink-gray-5",
					"aria-hidden": "true",
				}),
				h("span", { class: "min-w-0 truncate" }, __("Create “{0}”", [text])),
			]
		);
	return { label: __("Create “{0}”", [text]), value: CREATE_VALUE, slots: { item: row } };
}

// Watched: opened from the anchor, the picker never fires update:open.
watch(open, (opened) => {
	if (opened) {
		query.value = "";
		props.session.begin();
		search("");
	} else {
		target.value = "";
		if (!pending.value) void props.session.commit();
	}
});

if (props.shortcut) {
	useKeyboardShortcut({
		combo: "G",
		description: __("Add tags"),
		handler: () => (open.value = true),
	});
}

useEventListener(document, ["keydown", "pointermove"], releaseTarget, { capture: true });

// A refit or a closing panel can drop the picker mid-session; its ticks still save.
onBeforeUnmount(() => {
	if (!open.value && !pending.value) return;
	naming.value = recolouring.value = "";
	void props.session.commit();
});

defineExpose({ openOn });

/** Opens the picker scrolled to `tag`, with the highlight on it. */
function openOn(tag: string) {
	target.value = tag;
	if (open.value) highlightTarget();
	else open.value = true;
}

// reka moves the highlight to the first ticked row whenever the options change.
function onHighlight(option: { value: string | number } | null) {
	if (target.value && option?.value !== target.value) highlightTarget();
}

// The user's own key or hover takes the highlight back; reka's synthetic one does not.
function releaseTarget(event: Event) {
	const onRow = (event.target as Element | null)?.closest?.('[role="option"]');
	if (event.isTrusted && (event.type === "keydown" || onRow)) target.value = "";
}

// reka highlights a row on its pointermove and takes no value from outside MultiSelect.
function highlightTarget() {
	const row = [...document.querySelectorAll<HTMLElement>("[data-recolour]")]
		.find((button) => button.dataset.recolour === target.value)
		?.closest<HTMLElement>('[role="option"]');
	if (!row) return;
	row.dispatchEvent(new PointerEvent("pointermove", { bubbles: true }));
	row.scrollIntoView({ block: "nearest" });
}

function onPick(picked: (string | number)[]) {
	const next = picked.map(String);
	if (next.includes(CREATE_VALUE)) return startCreate();
	props.session.set(next);
}

function startCreate() {
	naming.value = query.value.trim();
	open.value = false;
}

function startRecolour(tag: string) {
	recolouring.value = tag;
	open.value = false;
}

// Only a picked colour creates the tag; Escape or a click away cancels it.
async function pickColor(color?: string) {
	const [tag, recolour] = [naming.value, recolouring.value];
	if (!tag && !recolour) return;
	naming.value = recolouring.value = "";
	if (color && tag) props.session.addNew(tag, color);
	else if (color) await props.session.recolour(recolour, color);
	if (!open.value) await props.session.commit();
}
</script>

<style>
/* A fixed width keeps the popover off the chips row; checked rows stay plain.
   min-width 0 drops frappe-ui's trigger-width floor, which is the whole tags row here. */
[data-slot="content"][data-selection]:has(.tag-picker-marker) {
	width: 13rem;
	min-width: 0;
}
[data-slot="content"][data-selection]:has(.tag-picker-marker)
	[role="option"][data-state="checked"] {
	background: transparent;
}
[data-slot="content"][data-selection]:has(.tag-picker-marker) [role="option"][data-highlighted] {
	background: var(--surface-alpha-gray-2);
}
[data-slot="content"][data-selection]:has(.tag-picker-marker) [data-slot="item-label"] {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
</style>
