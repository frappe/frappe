<!-- The navigation editor: the rail and every sidebar at one level. A draft takes every edit; Save is the one commit. -->
<template>
	<Dialog
		bare
		size="4xl"
		:modelValue="!!target"
		:dismissible="!changed"
		@update:modelValue="(open: boolean) => !open && close()"
	>
		<div class="flex h-[640px] flex-col" data-navigation-editor>
			<header
				class="flex items-start justify-between gap-4 border-b border-outline-gray-1 px-6 pb-4 pt-5"
			>
				<div class="min-w-0">
					<h2 class="text-xl font-semibold leading-7 text-ink-gray-9">
						{{ __("Customize navigation") }}
					</h2>
					<p class="mt-1 text-sm text-ink-gray-5">{{ boot.app_title }}</p>
				</div>
				<div class="flex flex-col items-end gap-1.5" data-level-switch>
					<div class="flex items-center gap-2">
						<Select
							:modelValue="draft?.layout ?? ''"
							class="w-52"
							side="bottom"
							align="end"
							:options="layoutOptions"
							:disabled="!draft || saving || resetting"
							data-layout-picker
							@update:modelValue="
								(layout: string) => draft && (draft = { ...draft, layout })
							"
						/>
						<Tooltip :text="levelHint" :disabled="!levelHint">
							<TabButtons
								:modelValue="scope"
								:options="levels"
								@update:modelValue="(value: Scope) => switchTo(value)"
							/>
						</Tooltip>
					</div>
					<p class="h-4 text-xs text-ink-gray-5">
						{{ scope === "site" ? __("Changes apply to everyone on this site") : "" }}
					</p>
				</div>
			</header>

			<p v-if="failed && !draft" class="m-auto text-sm text-ink-red-7">
				{{ __("Could not load the navigation: {0}", [failed]) }}
			</p>
			<span v-else-if="!draft" role="status" class="sr-only m-auto">{{
				__("Loading")
			}}</span>

			<div
				v-else
				class="grid min-h-0 flex-1 grid-cols-[300px_1fr]"
				:inert="saving || resetting"
			>
				<div class="flex min-h-0 flex-col border-r border-outline-gray-1">
					<div class="flex flex-col gap-2 px-6 pt-5">
						<div class="flex items-center justify-between">
							<div @dragover="overTabs" @dragleave="clearHover">
								<TabButtons v-model="tab" :options="tabs" />
							</div>
							<EditorAddMenu :options="addOptions" />
						</div>
						<Select
							v-if="tab === 'sidebar'"
							v-model="sidebar"
							side="bottom"
							:options="sidebarOptions"
							:placeholder="__('Choose a sidebar')"
						/>
						<p
							v-if="tab === 'sidebar' && hasNoPageToOpen(rows)"
							class="flex items-start gap-1.5 text-p-sm text-ink-gray-6"
							role="status"
							data-no-page-warning
						>
							<Icon name="triangle-alert" class="mt-0.5 size-3.5 shrink-0" />
							{{ __("This sidebar has no page to open") }}
						</p>
					</div>
					<div ref="listPane" class="min-h-0 flex-1 overflow-y-auto px-4 py-2">
						<EditorOutline
							:rows="rows"
							:show-hidden="showHidden"
							:selected="selected"
							:scope="scope"
							:icon-for="iconOf"
							:title-for="titleOf"
							@select="choose"
							@open="openForm"
							@move="move"
							@drag-start="(key: string) => (dragging = { container, key })"
							@drag-end="clearDrag"
							@drop="drop"
						/>
					</div>
					<div class="border-t border-outline-gray-1 px-6 py-3">
						<Checkbox v-model="showHidden" :label="__('Show hidden')" />
					</div>
				</div>

				<EditorRowForm
					v-if="adding"
					:key="adding.id"
					:type="adding.type"
					:type-label="
						addTypes(container).find((entry) => entry.type === adding!.type)?.label ??
						adding.type
					"
					:refusal="refusal"
					:scope="scope"
					:start="start"
					@add="add"
				/>
				<EditorRowPane
					v-else
					:row="current"
					:scope="scope"
					:parents="parentOptions"
					:can-place="container !== RAIL && current?.item_type !== 'Section'"
					:app-title="boot.app_title ?? ''"
					:refusal="refusal"
					:view-refusal="
						publishFirst && publishFirst.key === current?.key
							? publishFirst.message
							: null
					"
					:icon-for="iconOf"
					:title-for="titleOf"
					@update="(fields) => apply(update(draft!, container, selected!, fields))"
					@nest="(parent) => apply(nest(draft!, container, selected!, parent))"
					:move-targets="moveTargets"
					:can-give-sidebar="
						!!current && container === RAIL && canGiveSidebar(draft!, current)
					"
					:can-remove-sidebar="canRemoveOwnSidebar"
					:can-delete="!!current && isOwn(current.key, scope)"
					:delete-count="deleteCount"
					@toggle="toggle"
					@delete="remove"
					@move-to="moveTo"
					@give-sidebar="giveSidebar"
					@remove-sidebar="removeSidebar"
				/>
			</div>

			<p v-if="failed && draft" class="px-6 pb-2 text-sm text-ink-red-7" data-save-error>
				{{ failed }}
				<Button v-if="stale" variant="ghost" :label="__('Reload')" @click="reload" />
			</p>

			<footer class="flex items-center gap-2 border-t border-outline-gray-1 px-6 py-4">
				<Button
					v-if="changed"
					class="-ml-2"
					variant="ghost"
					:label="__('Discard changes')"
					:disabled="saving"
					data-revert
					@click="draft = revert(opened!)"
				/>
				<Button
					v-else-if="draft && hasSaved"
					class="-ml-2"
					variant="ghost"
					:label="__('Reset to default')"
					:loading="resetting"
					data-reset
					@click="reset"
				/>
				<Button
					class="ml-auto"
					variant="subtle"
					:label="__('Cancel')"
					:disabled="saving"
					@click="cancel"
				/>
				<Button
					variant="solid"
					:label="__('Save')"
					:loading="saving"
					:disabled="!changed || resetting"
					data-save
					@click="save"
				/>
			</footer>
		</div>
	</Dialog>
</template>

<script lang="ts">
/** Which list the editor opens on: the rail, or one sidebar by address or key. `null` keeps it closed. */
export type EditorTarget = { tab: "rail" } | { tab: "sidebar"; address: string };
</script>

<script setup lang="ts">
import { computed, inject, nextTick, onBeforeUnmount, onScopeDispose, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Button, Checkbox, dialog, Dialog, Select, TabButtons, Tooltip } from "frappe-ui";
import { isApiError } from "@framework/ui/api";
import {
	fetchArrangements,
	fetchDefaultArrangements,
	saveArrangements,
	saveNavigationLayout,
} from "@/arrangement";
import type { Addresses } from "@/addresses";
import type { Boot, Navigation } from "@/boot";
import { __ } from "@/i18n";
import Icon from "@/icons/Icon.vue";
import { iconOf as kindIcon } from "../registry";
import {
	type Draft,
	type EditorRow,
	dirty,
	fromArrangements,
	isOwn,
	isRowDrag,
	layoutChanged,
	openedSidebars,
	openerOf,
	sidebarOf,
	newKey,
	RAIL,
	resetToDefault,
	revert,
	rowsOf,
	type Scope,
	toPayload,
} from "./draft";
import {
	add as addRow,
	canGiveSidebar,
	carriesSidebar,
	descendantsToDelete,
	giveSidebar as giveRowSidebar,
	moveTo as moveRowTo,
	remove as removeRow,
	removeSidebar as removeRowSidebar,
	dropAcross,
	dropInto as dropRowInto,
	moveAmongSiblings,
	nest,
	refused,
	toggleHidden,
	update,
	type Edited,
} from "./edits";
import { addable, addTypes, servedPages } from "./addTypes";
import { hasNoPageToOpen } from "./actPicker";
import { PUBLISH_FIRST } from "./viewPicker";
import { thisPage } from "./thisPage";
import EditorAddMenu from "./EditorAddMenu.vue";
import EditorRowForm from "./EditorRowForm.vue";
import EditorOutline from "./EditorOutline.vue";
import EditorRowPane from "./EditorRowPane.vue";

const props = defineProps<{ target: EditorTarget | null }>();
const emit = defineEmits<{ close: []; saved: [Navigation] }>();

const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;
const CLOSING = __("Closing drops the edits you made. Nothing you changed is saved.");
const route = useRoute();
const router = useRouter();
const LAYOUTS: Record<string, string> = {
	rail_and_sidebar: __("Rail + sidebar"),
	sidebar_only: __("Sidebar only"),
	floating_rail: __("Floating rail"),
};

type Opened = { draft: Draft; opened: Draft; version: string; hasSaved: boolean };

const scope = ref<Scope>("user");
const reads = ref<Partial<Record<Scope, Opened>>>({});
const canEditSite = ref(true);
const layouts = ref<Record<string, string>>({});
const failed = ref<string | null>(null);
const stale = ref(false);
const saving = ref(false);
const resetting = ref(false);
const tab = ref<"rail" | "sidebar">("rail");
const sidebar = ref("");
const selected = ref<string | null>(null);
const showHidden = ref(false);
const refusal = ref<string | null>(null);
/** The save's refusal of an own view at Everyone: it shows under the View field of the row it is about. */
const publishFirst = ref<{ key: string; message: string } | null>(null);
/** The add form on show: its type, and an id per start so "Add this page" never keeps an old form's values. */
const adding = ref<{ type: string; id: number } | null>(null);
let adds = 0;
const start = ref<Omit<EditorRow, "key"> | undefined>();
// A reply that comes back after the editor was reopened belongs to the earlier opening.
// Every request notes the opening it started in, and touches the editor only while that one is open.
let opening = 0;
// Within one opening, only the newest read of a level may land.
const newest: Record<Scope, number> = { user: 0, site: 0 };
const keptLayout = ref<string>();
// Set once the editor is told to close, so the hash change that closes it is not asked about again.
// Any finished navigation clears it, also a refused one, so a close that did not happen cannot leave the guard off.
let closing = false;
let asking: { close: () => void } | undefined;

// Back and any other hash change that would close or reload the editor ask first, as Cancel does.
const removeGuard = router.beforeEach((to, from) => {
	if (closing || !props.target || !changed.value || to.hash === from.hash) return;
	// Cancel is off while a save runs, and so is every other way out.
	if (saving.value) return false;
	askToDiscard(CLOSING, __("Discard and close"), () => {
		closing = true;
		// After Back the entry behind the editor already holds `to`: step back onto it, so it is not copied over the editor's own.
		if (router.options.history.state.back === to.fullPath) router.back();
		else router.replace(to);
	});
	return false;
});
const removeClosed = router.afterEach(() => {
	closing = false;
});
onScopeDispose(() => {
	removeGuard();
	removeClosed();
});

const draft = computed<Draft | undefined>({
	get: () => reads.value[scope.value]?.draft,
	set: (next) => next && (reads.value[scope.value]!.draft = next),
});
const opened = computed(() => reads.value[scope.value]?.opened);
const hasSaved = computed(() => !!reads.value[scope.value]?.hasSaved);
const changed = computed(
	() => !!draft.value && !!opened.value && dirty(opened.value, draft.value)
);
const container = computed(() => (tab.value === "rail" ? RAIL : sidebar.value));
const rows = computed(() => (draft.value ? rowsOf(draft.value, container.value) : []));
const current = computed(() => rows.value.find((row) => row.key === selected.value));

// The Sidebar tab is for sidebars a rail row opens; a draft that opens none has no tab.
const openedKeys = computed(() => (draft.value ? openedSidebars(draft.value) : []));
const hasSidebars = computed(() => openedKeys.value.length > 0);
const tabs = computed(() => [
	{ label: __("Rail"), value: "rail" },
	...(hasSidebars.value ? [{ label: __("Sidebar"), value: "sidebar" }] : []),
]);
const sidebarOptions = computed(() =>
	openedKeys.value.map((key) => ({
		label: sidebarLabel(key),
		value: key,
	}))
);
const levels = computed(() => [
	{ label: __("Just me"), value: "user", disabled: changed.value || resetting.value },
	{
		label: __("Everyone"),
		value: "site",
		disabled: changed.value || resetting.value || !canEditSite.value,
	},
]);
const levelHint = computed(() =>
	changed.value
		? __("Save or discard your changes first.")
		: canEditSite.value
		? ""
		: __("Only System Managers can change it for everyone")
);
const layoutOptions = computed(() => {
	const below =
		scope.value === "user"
			? layouts.value.site || layouts.value.standard
			: layouts.value.standard;
	const name = LAYOUTS[below || "rail_and_sidebar"];
	return [
		{ label: __("Default ({0})", [name]), value: "" },
		...Object.entries(LAYOUTS).map(([value, label]) => ({ label, value })),
	];
});
const parentOptions = computed(() => [
	{ label: __("Top level"), value: "" },
	...rows.value
		// An act only runs: no row sits under it.
		.filter((row) => row.key !== selected.value && !row.no_access && row.item_type !== "Act")
		.map((row) => ({ label: titleOf(row), value: row.key })),
]);

watch(
	() => props.target,
	(target) => {
		if (!target) return;
		opening += 1;
		closing = false;
		keptLayout.value = undefined;
		reads.value = {};
		saving.value = false;
		resetting.value = false;
		refusal.value = null;
		stopAdding();
		scope.value = "user";
		selected.value = null;
		showHidden.value = false;
		tab.value = target.tab;
		if (target.tab === "sidebar") sidebar.value = target.address;
		load("user");
	},
	{ immediate: true }
);

// The other tab offers other types: a form left open would add to a list it was not started on.
watch(tab, () => {
	selected.value = null;
	stopAdding();
});
// A sidebar a Discard, a reset or a removal took away leaves the picker for one still there.
watch(openedKeys, () => draft.value && fitSidebar(draft.value));

/** An added or moved row can sit past the fold, and another list keeps the old scroll: show the selected row, else the top. */
const listPane = ref<HTMLElement | null>(null);
watch([container, selected], async () => {
	await nextTick();
	const row =
		selected.value &&
		listPane.value?.querySelector(`[data-key="${CSS.escape(selected.value)}"]`);
	if (row) row.scrollIntoView?.({ block: "nearest" });
	else listPane.value?.scrollTo?.({ top: 0 });
});
// A rail edit that stops opening the last sidebar takes its tab away.
// While a read is on its way the draft is empty, which is not an edit.
watch(hasSidebars, (has) => !has && draft.value && (tab.value = "rail"));
// The selection and the add form belong to the sidebar in view; a refit while on the rail keeps them.
watch(sidebar, () => {
	if (tab.value !== "sidebar") return;
	selected.value = null;
	stopAdding();
});
// A selected row that the list now hides leaves the pane for its nearest visible neighbour.
watch(showHidden, (on) => !on && selected.value && leaveIfUnlisted(selected.value));

/** `layout` keeps an edited layout over the fresh read, for a reload that follows a half save. */
async function load(level: Scope, layout?: string): Promise<boolean> {
	const current = opening;
	const ticket = ++newest[level];
	const latest = () => current === opening && ticket === newest[level];
	failed.value = null;
	publishFirst.value = null;
	stale.value = false;
	try {
		const response = await fetchArrangements(boot.app!, level);
		if (!latest()) return false;
		keptLayout.value = undefined;
		const read = fromArrangements(response, level);
		const edited = layout === undefined ? read : { ...read, layout };
		reads.value = {
			...reads.value,
			[level]: {
				draft: edited,
				opened: read,
				version: response.version,
				hasSaved: response.has_saved,
			},
		};
		canEditSite.value = response.can_edit_site;
		layouts.value = response.navigation_layouts;
		fitSidebar(read);
		return true;
	} catch (error) {
		if (latest()) failed.value = (error as Error).message;
		return false;
	}
}

/** The level in view may open other sidebars than the last one: keep the picked sidebar only if it is still there. */
function fitSidebar(read: Draft) {
	const offered = openedSidebars(read);
	if (!offered.includes(sidebar.value)) sidebar.value = offered[0] ?? "";
	if (tab.value === "sidebar" && !offered.length) tab.value = "rail";
}

async function switchTo(value: Scope) {
	if (changed.value || value === scope.value) return;
	scope.value = value;
	selected.value = null;
	stopAdding();
	const cached = reads.value[value];
	if (cached) fitSidebar(cached.draft);
	else await load(value);
}

function choose(key: string) {
	selected.value = key;
	stopAdding();
	refusal.value = null;
}

function stopAdding() {
	adding.value = null;
	start.value = undefined;
}

const here = computed(() => thisPage(route, addresses, boot.app));

const addOptions = computed(() => {
	const hasPages = servedPages((name) => router.hasRoute(name), boot.app).length > 0;
	const types = addTypes(container.value)
		.filter((entry) => entry.type !== "Page" || hasPages)
		.map((entry) => ({
			label: entry.label,
			icon: entry.icon,
			onClick: () => startAdding(entry.type),
		}));
	const page = here.value;
	if (!page) return types;
	return [
		{
			group: __("This page"),
			options: [
				{
					label: __("Add this page ({0})", [page.label]),
					icon: "lucide-pin",
					onClick: () => startAdding(page.type, page.fields),
				},
			],
		},
		{ group: __("New row"), options: types },
	];
});

function startAdding(type: string, fields?: Omit<EditorRow, "key">) {
	adding.value = { type, id: ++adds };
	start.value = fields;
	refusal.value = null;
}

/** A new row goes last in the list, or last under the selected section. */
function add(fields: Omit<EditorRow, "key">) {
	if (!draft.value) return;
	const row = { ...fields, key: newKey(scope.value) } as EditorRow;
	// A section sits at the top level, so only another kind goes under the selected section.
	const parent =
		current.value?.item_type === "Section" &&
		row.item_type !== "Section" &&
		container.value !== RAIL
			? current.value.key
			: null;
	const edited = addRow(draft.value, container.value, row, parent);
	apply(edited);
	if (refused(edited)) return;
	stopAdding();
	selected.value = row.key;
	// The form that held focus is gone: the new row takes it.
	nextTick(() => document.getElementById(`editor-row-${row.key}`)?.focus());
}

/** Where Move to… offers the row: an inherited row the server cannot take as a copy goes nowhere, and a row that opens a sidebar into none. */
const moveTargets = computed(() => {
	const row = current.value;
	if (!draft.value || !row) return [];
	const own = isOwn(row.key, scope.value);
	if (!own && !addable(row.item_type)) return [];
	return [RAIL, ...openedKeys.value]
		.filter(
			(target) =>
				target !== container.value &&
				target !== sidebarOf(row) &&
				(target === RAIL || !carriesSidebar(row, scope.value))
		)
		.map((target) => ({
			label: target === RAIL ? __("Rail") : sidebarLabel(target),
			value: target,
		}));
});
const canRemoveOwnSidebar = computed(() => {
	const opens = container.value === RAIL ? current.value?.opens_sidebar : undefined;
	return !!opens && isOwn(opens, scope.value);
});
const deleteCount = computed(() =>
	current.value && isOwn(current.value.key, scope.value)
		? 1 + descendantsToDelete(rows.value, current.value.key, scope.value).length
		: 1
);

/** Selection after an edit that removes the row from this list moves to its neighbour. */
function remove() {
	const key = selected.value;
	if (!draft.value || !key) return;
	const edited = removeRow(draft.value, container.value, key);
	const before = rows.value;
	apply(edited);
	if (refused(edited)) return;
	// The nearest row the list still shows: the deleted row's own children went with it.
	const kept = new Set(
		rowsOf(edited, container.value)
			.filter((row) => showHidden.value || !row.hidden)
			.map((row) => row.key)
	);
	const at = before.findIndex((row) => row.key === key);
	const neighbour =
		before.slice(at + 1).find((row) => kept.has(row.key)) ??
		before
			.slice(0, at)
			.reverse()
			.find((row) => kept.has(row.key));
	selected.value = neighbour?.key ?? null;
}

function moveTo(target: string) {
	const key = selected.value;
	if (!draft.value || !key) return;
	const moved = moveRowTo(draft.value, container.value, key, target);
	refusal.value = refused(moved) ? moved : null;
	if (refused(moved)) return;
	draft.value = moved.draft;
	show(target, moved.key);
}

function giveSidebar() {
	if (!draft.value || !selected.value) return;
	const next = giveRowSidebar(draft.value, selected.value);
	refusal.value = refused(next) ? next : null;
	if (refused(next)) return;
	draft.value = next.draft;
	show(
		rowsOf(next.draft, RAIL).find((row) => row.key === selected.value)!.opens_sidebar!,
		next.key
	);
}

function removeSidebar() {
	if (!draft.value || !selected.value) return;
	apply(removeRowSidebar(draft.value, selected.value));
}

function switchContainer(target: string) {
	tab.value = target === RAIL ? "rail" : "sidebar";
	if (target !== RAIL) sidebar.value = target;
}

/** Show a container with a row selected: a tab change clears the selection, so it is set once that settles. */
async function show(target: string, key: string) {
	stopAdding();
	switchContainer(target);
	await nextTick();
	selected.value = key;
}

/** Enter on a row: select it, then put the cursor in the form's first field. */
async function openForm(key: string) {
	choose(key);
	await nextTick();
	document
		.querySelector<HTMLInputElement>(
			"[data-editor-pane] [data-field='label'] input, [data-editor-pane] input[data-field='label']"
		)
		?.focus();
}

/** An edit that refuses leaves the draft alone and says why under the field. */
function apply(edited: Edited) {
	publishFirst.value = null;
	refusal.value = refused(edited) ? edited : null;
	if (!refused(edited)) draft.value = edited;
}

function move(key: string, by: 1 | -1) {
	if (draft.value)
		draft.value = moveAmongSiblings(draft.value, container.value, key, by, showHidden.value);
}

function toggle() {
	const key = selected.value!;
	apply(toggleHidden(draft.value!, container.value, key));
	leaveIfUnlisted(key);
}

/** The pane follows the list: a row the list no longer shows hands the selection to the next one. */
function leaveIfUnlisted(key: string) {
	const listed = rows.value.filter((row) => showHidden.value || !row.hidden);
	if (listed.some((row) => row.key === key)) return;

	// `rows` still holds the row, so its place in the full list finds its neighbours.
	const at = rows.value.findIndex((row) => row.key === key);
	const neighbour =
		rows.value.slice(at + 1).find((row) => listed.includes(row)) ??
		rows.value
			.slice(0, at)
			.reverse()
			.find((row) => listed.includes(row));
	selected.value = neighbour?.key ?? null;
}

const dragging = ref<{ container: string; key: string } | null>(null);
let hoverTimer: ReturnType<typeof setTimeout> | undefined;
let hovered: string | undefined;

function clearHover() {
	clearTimeout(hoverTimer);
	hovered = undefined;
}

function clearDrag() {
	dragging.value = null;
	clearHover();
}

// A drag the list no longer holds the row of (a tab change took it away) ends on the window, not on the row.
window.addEventListener("dragend", clearDrag);
onBeforeUnmount(() => {
	window.removeEventListener("dragend", clearDrag);
	clearHover();
});

/** Held over the other tab for 500 ms, a drag switches to it. */
function overTabs(event: DragEvent) {
	if (!dragging.value || !isRowDrag(event)) return;
	const buttons = [...(event.currentTarget as HTMLElement).querySelectorAll("button")];
	const over = buttons.indexOf((event.target as HTMLElement).closest("button")!);
	const next = tabs.value[over]?.value as "rail" | "sidebar" | undefined;
	if (!next || next === tab.value) return clearHover();
	if (hovered === next) return;
	clearHover();
	hovered = next;
	hoverTimer = setTimeout(() => {
		tab.value = next;
		hovered = undefined;
	}, 500);
}

/** A drop before a row, or on the middle of a rail row that opens a sidebar, from either container. */
function drop(onKey: string, middle: boolean) {
	const from = dragging.value;
	clearDrag();
	if (!draft.value || !from || from.key === onKey) return;
	const opens = sidebarOf(rowsOf(draft.value, RAIL).find((row) => row.key === onKey));
	const inside = middle && container.value === RAIL && !!opens && opens in draft.value.sidebars;
	const moved = inside
		? dropRowInto(draft.value, from.container, from.key, onKey)
		: dropAcross(draft.value, from.container, from.key, container.value, onKey);
	if (refused(moved)) {
		// The refusal shows under "Place under" of the dragged row, so go back to it.
		show(from.container, from.key);
		refusal.value = moved;
		return;
	}
	refusal.value = null;
	draft.value = moved.draft;
	show(inside ? opens! : container.value, moved.key);
}

/** The level below is read only now, so opening the editor costs nothing for it; Save commits the reset. */
async function reset() {
	const level = scope.value;
	const read = reads.value[level];
	if (!read) return;
	const current = opening;
	resetting.value = true;
	failed.value = null;
	try {
		const below = await fetchDefaultArrangements(boot.app!, level);
		if (current !== opening) return;
		read.draft = resetToDefault(read.draft, below);
		selected.value = null;
	} catch (error) {
		if (current === opening) failed.value = (error as Error).message;
	} finally {
		if (current === opening) resetting.value = false;
	}
}

/** The rows first, then the layout, each only when its part changed; the last answer is the navigation. */
async function save() {
	const level = scope.value;
	const read = reads.value[level];
	if (!read) return;
	const { draft: edited, opened: before } = read;
	const current = opening;
	saving.value = true;
	failed.value = null;
	publishFirst.value = null;
	let navigation: Navigation | undefined;
	try {
		const payload = toPayload(before, edited);
		if (Object.keys(payload).length)
			navigation = await saveArrangements(boot.app!, level, payload, read.version);
		if (layoutChanged(before, edited))
			navigation = await saveNavigationLayout(boot.app!, edited.layout, level);
		if (navigation) emit("saved", navigation);
		if (current === opening) close();
	} catch (error) {
		// The shell takes rows that went in, even when the editor was reopened since.
		if (navigation) emit("saved", navigation);
		if (current !== opening) return;
		failed.value = (error as Error).message;
		stale.value = isApiError(error) && !!error.isTimestampMismatch;
		if (!navigation) showPublishFirst(before, edited, level);
		// The rows are in: the next Save needs the version they made.
		if (navigation) await keepSavedRows(level, edited, failed.value, current);
	} finally {
		if (current === opening) saving.value = false;
	}
}

/** The server names no row in this refusal: it is about an own View row, the first one added since the last save. */
function showPublishFirst(before: Draft, edited: Draft, level: Scope) {
	if (failed.value !== PUBLISH_FIRST()) return;
	const changed = toPayload(before, edited);
	const rows = [...(changed.rail ?? []), ...Object.values(changed.sidebars ?? {}).flat()];
	const saved = new Set(
		[...before.rail, ...Object.values(before.sidebars).flat()].map((entry) => entry.key)
	);
	const own = rows.filter((entry) => entry.item_type === "View" && isOwn(entry.key, level));
	const row = own.find((entry) => !saved.has(entry.key)) ?? own[0];
	if (!row) return;
	publishFirst.value = { key: row.key, message: failed.value };
	failed.value = null;
	const sidebars = changed.sidebars ?? {};
	const holder = (changed.rail ?? []).includes(row)
		? RAIL
		: Object.keys(sidebars).find((key) => sidebars[key].includes(row))!;
	void show(holder, row.key);
}

/** Reload reads the level again and drops the draft, so a draft with edits asks first. */
function reload() {
	const level = scope.value;
	const layout = keptLayout.value;
	if (!changed.value) return void load(level, layout);
	askToDiscard(
		__("Reloading drops the edits you made. Nothing you changed is saved."),
		__("Discard and reload"),
		() => void load(level, layout)
	);
}

function close() {
	closing = true;
	emit("close");
}

function cancel() {
	if (!changed.value) return close();
	askToDiscard(CLOSING, __("Discard and close"), close);
}

/** One confirm for every exit that drops the draft; it does nothing if the editor was reopened meanwhile. */
function askToDiscard(message: string, label: string, discard: () => void) {
	const current = opening;
	asking?.close();
	asking = dialog.confirm({
		title: __("Discard your changes?"),
		message,
		actions: [
			{ label: __("Keep editing"), variant: "subtle" },
			{
				label,
				variant: "subtle",
				theme: "red",
				onClick: () => void (current === opening && discard()),
			},
		],
	});
}

/** The layout save failed after the rows went in. The layout stays edited, on top of a fresh read. */
async function keepSavedRows(level: Scope, edited: Draft, reason: string, current: number) {
	const reloaded = await load(level, edited.layout);
	if (current !== opening) return;
	if (!reloaded) keptLayout.value = edited.layout;
	failed.value = __("Your rows are saved, but the layout is not: {0}", [reason]);
	stale.value = !reloaded;
}

function titleOf(row: EditorRow): string {
	return row.label || row.link_to || row.url || row.key;
}

function iconOf(row: EditorRow): string {
	return kindIcon(row);
}

/** A sidebar is named for the rail row that opens it. */
function sidebarLabel(key: string): string {
	const opener = draft.value && openerOf(draft.value, key);
	return opener ? titleOf(opener) : key;
}
</script>
