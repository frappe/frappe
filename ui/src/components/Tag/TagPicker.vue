<template>
	<TagColorPicker v-model:open="colorPickerOpen" :tag="pendingTag" @select="pickColor">
		<!-- plain div anchor: MultiSelect's root is display:contents, which
         would give the PopoverAnchor a zero rect -->
		<div>
			<MultiSelect
				v-model="localTags"
				v-model:open="tagPickerOpen"
				:options="tagOptions"
				:loading="tagListResource.loading"
				placeholder="Search or create tags"
				side="left"
				v-model:query="queryText"
			>
				<template #trigger>
					<!-- reka turns TagColorPicker's whole wrapper into a trigger, so a
               click here would open the colour picker as well -->
					<div class="flex min-w-0 flex-1 flex-wrap items-center gap-1.5" @click.stop>
						<Tag
							v-for="tag in headTags"
							:key="tag"
							:label="tag"
							:color="tagColor(tag)"
						/>
						<!-- last chip + trailing control form one flex item so neither
                 wraps onto a line of its own -->
						<div class="flex min-w-0 max-w-full items-center gap-1.5">
							<Transition name="tag-chip">
								<Tag
									v-if="lastTag"
									:key="lastTag"
									:label="lastTag"
									:color="tagColor(lastTag)"
								/>
							</Transition>
							<Tooltip v-if="!hiddenTags.length" text="Add">
								<button
									v-if="!localTags.length"
									class="inline-flex items-center text-base text-ink-gray-6 transition-[color,transform] duration-150 hover:text-ink-gray-8 active:scale-[0.96]"
								>
									+ Add
								</button>
								<button
									v-else
									class="inline-flex h-6 w-6 items-center justify-center rounded-full text-ink-gray-5 transition-[color,background-color,transform] duration-150 hover:bg-surface-gray-2 hover:text-ink-gray-7 active:scale-[0.96]"
								>
									<LucidePlus class="size-3.5" />
								</button>
							</Tooltip>
						</div>
						<!-- own wrap item: grouped with the last chip it would inflate
                 the row's min-content width past the panel edge -->
						<Tooltip v-if="hiddenTags.length" :text="hiddenTags.join(', ')">
							<Badge
								theme="gray"
								variant="outline"
								size="lg"
								class="shrink-0 text-ink-gray-7 transition-colors duration-150 hover:bg-surface-gray-2"
							>
								+{{ hiddenTags.length }} more
							</Badge>
						</Tooltip>
					</div>
				</template>
				<template #item-prefix="{ item }">
					<span class="size-2.5 shrink-0 rounded-full" :class="colorToken(item.color)" />
				</template>
				<template #empty>
					<span class="text-p-sm"> No tags yet, type to create one </span>
				</template>
				<!-- marker scopes this picker's style overrides (see <style>);
             the popover is portaled, scoped styles can't reach it -->
				<template #footer>
					<span class="ticket-tags-marker hidden" aria-hidden="true" />
				</template>
			</MultiSelect>
		</div>
	</TagColorPicker>
</template>

<script setup lang="ts">
// Editing runs as a session: it opens with the picker and ends once both the
// picker and TagColorPicker are closed. `localTags` is the source of truth
// while it runs, `appliedAtOpen` is the snapshot to diff against, and the close
// sends one add/remove batch.
import { colorToken } from "./colors";
import { useEventListener } from "@vueuse/core";
import { Badge, call, createResource, MultiSelect, toast, Tooltip } from "frappe-ui";
import { computed, h, onBeforeUnmount, ref, watch } from "vue";
import LucidePlus from "~icons/lucide/plus";
import Tag from "./Tag.vue";
import TagColorPicker from "./TagColorPicker.vue";
import type { Tag as TagRecord } from "./types";

// sentinel option value: picking it starts tag creation instead of a toggle
const CREATE_VALUE = "__create__";

// collapse only past VISIBLE_TAGS + 1 so "+1 more" never replaces the one
// chip it hides
const VISIBLE_TAGS = 3;

const props = defineProps<{
	doctype: string;
	docname: string;
	app: string;
	tags?: string | undefined;
}>();
const emit = defineEmits<{ change: []; "update:tags": [tags: string] }>();

const tagListResource = createResource({
	url: "frappe.desk.doctype.tag.tag.get_tags_for_app",
	params: { app: props.app },
	auto: true,
});

const tagPickerOpen = ref(false);
const colorPickerOpen = ref(false);
const queryText = ref("");
const localTags = ref<string[]>([]);
const appliedAtOpen = ref<string[]>([]);
let syncing = false;

const pendingTag = ref("");
// colour for a not-yet-created tag; update_tags applies colour on create only
const pendingColors = ref<Record<string, string>>({});

const appliedTags = computed<string[]>(() => [
	...new Set(
		(props.tags || "")
			.split(",")
			.map((tag) => tag.trim())
			.filter(Boolean)
	),
]);

const visibleTags = computed(() =>
	localTags.value.length > VISIBLE_TAGS + 1
		? localTags.value.slice(0, VISIBLE_TAGS)
		: localTags.value
);
const hiddenTags = computed(() => localTags.value.slice(visibleTags.value.length));
const headTags = computed(() => visibleTags.value.slice(0, -1));
const lastTag = computed(() => visibleTags.value.at(-1));

const existingTagOptions = computed(() => {
	const applied = new Set(appliedAtOpen.value);
	const tags: TagRecord[] = [...((tagListResource.data || []) as TagRecord[])];
	// applied tags minted outside helpdesk are listable too; the close claims them
	const known = new Set(tags.map((tag) => tag.name));
	for (const name of appliedAtOpen.value) {
		if (!known.has(name)) tags.push({ name });
	}
	return tags
		.sort(
			(a, b) =>
				Number(applied.has(b.name)) - Number(applied.has(a.name)) ||
				a.name.localeCompare(b.name)
		)
		.map((tag) => ({
			label: tag.name,
			value: tag.name,
			color: tag.color,
		}));
});

// the create row's label ends with the *raw* query: the list matcher tests
// it untrimmed, so a trailing space would otherwise filter the row out
const tagOptions = computed(() => {
	const options: Record<string, unknown>[] = [...existingTagOptions.value];
	const text = queryText.value.trim();
	if (showCreateOption.value) {
		options.push({
			label: `Create ${queryText.value}`,
			value: CREATE_VALUE,
			slots: {
				item: () =>
					h(
						"span",
						{
							class: "flex min-h-7 w-full min-w-0 items-center gap-2 px-2 py-1.5 text-base text-ink-gray-7",
						},
						[
							h(LucidePlus, { class: "size-3.5 shrink-0 text-ink-gray-5" }),
							h("span", { class: "min-w-0 truncate" }, `Create "${text}"`),
						]
					),
			},
		});
	}
	return options;
});

function tagColor(tag: string) {
	return ((tagListResource.data || []) as TagRecord[]).find((t) => t.name === tag)?.color;
}

const showCreateOption = computed(() => {
	const text = queryText.value.trim().toLowerCase();
	if (!text) return false;
	return ![...existingTagOptions.value.map((o) => o.value), ...localTags.value].some(
		(name) => name.toLowerCase() === text
	);
});

const queryMatchesExistingTag = computed(() => {
	const text = queryText.value.trim().toLowerCase();
	return existingTagOptions.value.some((o) => o.value.toLowerCase().includes(text));
});

function startCreate() {
	const tag = queryText.value.trim();
	if (colorPickerOpen.value || !tag || localTags.value.includes(tag)) return;
	// _user_tags is a comma-separated column; a comma would split the tag apart
	if (tag.includes(",")) {
		toast.error("Tag cannot contain commas");
		return;
	}
	pendingTag.value = tag;
	tagPickerOpen.value = false;
	colorPickerOpen.value = true;
}

// closing the popover ends the session, so the tag must be added synchronously
// here: the watcher that syncs only runs on the next flush
function pickColor(color: string) {
	const tag = pendingTag.value;
	colorPickerOpen.value = false;
	if (!tag || localTags.value.includes(tag)) return;
	pendingColors.value[tag] = color;
	// seed the list so the new chip's dot is coloured before the reload lands
	if (!(tagListResource.data || []).some((t: TagRecord) => t.name === tag)) {
		tagListResource.data = [...(tagListResource.data || []), { name: tag, color }];
	}
	localTags.value = [...localTags.value, tag];
}

async function syncTagChanges() {
	const base = appliedAtOpen.value;
	const next = localTags.value;
	// Still-applied tags outside this app ride along as adds so the API can claim them.
	const known = new Set(((tagListResource.data || []) as TagRecord[]).map((tag) => tag.name));
	const claims = next.filter((tag) => base.includes(tag) && !known.has(tag));
	const added = [
		...next
			.filter((tag) => !base.includes(tag))
			.map((name) => ({ name, color: pendingColors.value[name] })),
		...claims.map((name) => ({ name })),
	];
	const removed = base.filter((tag) => !next.includes(tag));
	pendingColors.value = {};
	if (!added.length && !removed.length) {
		adoptServerTags();
		return;
	}
	// rebase so a session reopened mid-request doesn't resend this batch
	appliedAtOpen.value = [...next];
	syncing = true;
	try {
		await call("frappe.desk.doctype.tag.tag.update_document_tags", {
			doctype: props.doctype,
			docname: props.docname,
			app: props.app,
			added,
			removed,
		});
		emit("update:tags", next.join(","));
		emit("change");
	} catch (error: any) {
		toast.error(error?.messages?.join(", ") || "Failed to update tags");
		// the failed batch left the document unchanged, so no `tags` change will
		// roll the optimistic chips back
		localTags.value = [...appliedTags.value];
	} finally {
		syncing = false;
	}
}

// mid-session this would make reka re-highlight the first checked row, and a
// stale reload would briefly resurrect just-removed chips
function adoptServerTags() {
	if (tagPickerOpen.value || colorPickerOpen.value || syncing) return;
	const tags = appliedTags.value;
	const local = localTags.value;
	if (tags.length === local.length && tags.every((t) => local.includes(t))) return;
	localTags.value = [...tags];
}

// capture + immediate: pre-empts reka's Enter handler and useShortcut, and
// stops TagColorPicker, which Vue would have flushed open before the next
// listener runs, from picking a colour on this same keypress
useEventListener(
	document,
	"keydown",
	(event: KeyboardEvent) => {
		if (!tagPickerOpen.value || event.key !== "Enter") return;
		if (queryMatchesExistingTag.value || !showCreateOption.value) return;
		event.preventDefault();
		event.stopImmediatePropagation();
		startCreate();
	},
	{ capture: true }
);

watch(appliedTags, adoptServerTags, { immediate: true });

watch(localTags, (next) => {
	// selecting the create row is a model change; divert it to the color step
	if (next.includes(CREATE_VALUE)) {
		localTags.value = next.filter((tag) => tag !== CREATE_VALUE);
		startCreate();
	}
});

watch(tagPickerOpen, (open) => {
	queryText.value = "";
	if (open) {
		// mid-session the colour step still owns the batch; rebasing here would
		// drop whatever was unticked before the create started
		if (!colorPickerOpen.value) appliedAtOpen.value = [...localTags.value];
		tagListResource.reload();
	} else if (!colorPickerOpen.value) {
		// the create flow hands the session to the colour popover
		syncTagChanges();
	}
});

watch(colorPickerOpen, (open) => {
	if (!open) {
		pendingTag.value = "";
		syncTagChanges();
	}
});

onBeforeUnmount(() => {
	if (tagPickerOpen.value || colorPickerOpen.value) syncTagChanges();
});
</script>

<style>
/* Overrides scoped via the marker in the footer slot: the popover is
   portaled to body, so scoped styles can't reach it. Checked rows stay
   plain; the checkbox alone carries the state. */
[data-slot="content"][data-selection]:has(.ticket-tags-marker)
	[role="option"][data-state="checked"] {
	background: transparent;
}
[data-slot="content"][data-selection]:has(.ticket-tags-marker) [role="option"][data-highlighted] {
	background: var(--surface-alpha-gray-2);
}
/* fixed width so the popover doesn't track the chips row */
[data-slot="content"][data-selection]:has(.ticket-tags-marker) {
	width: 13rem;
}
[data-slot="content"][data-selection]:has(.ticket-tags-marker) [data-slot="item-label"] {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
/* outline-gray-1 vanishes on the dark elevation-2 surface */
[data-slot="content"][data-selection]:has(.ticket-tags-marker) [data-slot="search"] {
	@apply border-outline-gray-2;
}
</style>

<style scoped>
/* enter only: a chip swapping between head list and tail group must not
   play a leave animation, or it would briefly render twice */
.tag-chip-enter-active {
	transition: opacity 180ms cubic-bezier(0.23, 1, 0.32, 1),
		transform 180ms cubic-bezier(0.23, 1, 0.32, 1);
}
.tag-chip-enter-from {
	opacity: 0;
	transform: scale(0.96);
}
.tag-chip-leave-active {
	display: none;
}

@media (prefers-reduced-motion: reduce) {
	.tag-chip-enter-active {
		transition-duration: 0ms;
	}
}
</style>
