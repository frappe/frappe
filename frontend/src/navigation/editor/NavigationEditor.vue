<!-- The navigation editor: the rail and every sidebar at one level. A draft takes every edit; Save is the one commit. -->
<template>
	<Dialog
		bare
		size="4xl"
		:modelValue="!!target"
		:dismissible="!changed"
		@update:modelValue="(open: boolean) => !open && emit('close')"
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
							:disabled="!draft || saving"
							data-layout-picker
							@update:modelValue="(layout: string) => draft && (draft = { ...draft, layout })"
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

			<p v-if="failed && !draft" class="m-auto text-sm text-ink-red-4">
				{{ __("Could not load the navigation: {0}", [failed]) }}
			</p>
			<span v-else-if="!draft" role="status" class="sr-only m-auto">{{
				__("Loading")
			}}</span>

			<div v-else class="grid min-h-0 flex-1 grid-cols-[300px_1fr]" :inert="saving">
				<div class="flex min-h-0 flex-col border-r border-outline-gray-1">
					<div class="flex flex-col gap-2 px-6 pt-5">
						<div class="flex items-center justify-between">
							<TabButtons v-model="tab" :options="tabs" />
							<EditorAddMenu :options="[]" />
						</div>
						<Select
							v-if="tab === 'sidebar'"
							v-model="sidebar"
							side="bottom"
							:options="sidebarOptions"
							:placeholder="__('Choose a sidebar')"
						/>
					</div>
					<div class="min-h-0 flex-1 overflow-y-auto px-4 py-2">
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
							@drop-before="drop"
						/>
					</div>
					<div class="border-t border-outline-gray-1 px-6 py-3">
						<Checkbox v-model="showHidden" :label="__('Show hidden')" />
					</div>
				</div>

				<EditorRowPane
					:row="current"
					:parents="parentOptions"
					:can-place="container !== RAIL && current?.item_type !== 'Section'"
					:app-title="boot.app_title ?? ''"
					:refusal="refusal"
					:icon-for="iconOf"
					:title-for="titleOf"
					@update="(fields) => apply(update(draft!, container, selected!, fields))"
					@nest="(parent) => apply(nest(draft!, container, selected!, parent))"
					@toggle="toggle"
				/>
			</div>

			<p v-if="failed && draft" class="px-6 pb-2 text-sm text-ink-red-4" data-save-error>
				{{ failed }}
				<Button
					v-if="stale"
					variant="ghost"
					:label="__('Reload')"
					@click="load(scope, keptLayout)"
				/>
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
					@click="emit('close')"
				/>
				<Button
					variant="solid"
					:label="__('Save')"
					:loading="saving"
					:disabled="!changed"
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
import { computed, inject, nextTick, ref, watch } from "vue";
import { Button, Checkbox, Dialog, Select, TabButtons, Tooltip } from "frappe-ui";
import { isApiError } from "@framework/ui/api";
import {
	fetchArrangements,
	fetchDefaultArrangements,
	saveArrangements,
	saveNavigationLayout,
} from "@/arrangement";
import type { Boot, Navigation } from "@/boot";
import { __ } from "@/i18n";
import { iconOf as kindIcon } from "../registry";
import {
	type Draft,
	type EditorRow,
	dirty,
	fromArrangements,
	layoutChanged,
	openedSidebars,
	openerOf,
	RAIL,
	resetToDefault,
	revert,
	rowsOf,
	type Scope,
	toPayload,
} from "./draft";
import {
	dropBefore,
	moveAmongSiblings,
	nest,
	refused,
	toggleHidden,
	update,
	type Edited,
} from "./edits";
import EditorAddMenu from "./EditorAddMenu.vue";
import EditorOutline from "./EditorOutline.vue";
import EditorRowPane from "./EditorRowPane.vue";

const props = defineProps<{ target: EditorTarget | null }>();
const emit = defineEmits<{ close: []; saved: [Navigation] }>();

const boot = inject<Boot>("boot")!;
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
// A reply that comes back after the editor was reopened belongs to the earlier opening.
// Every request notes the opening it started in, and touches the editor only while that one is open.
let opening = 0;
// Within one opening, only the newest read of a level may land.
const newest: Record<Scope, number> = { user: 0, site: 0 };
const keptLayout = ref<string>();

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
		.filter((row) => row.key !== selected.value && !row.no_access)
		.map((row) => ({ label: titleOf(row), value: row.key })),
]);

watch(
	() => props.target,
	(target) => {
		if (!target) return;
		opening += 1;
		keptLayout.value = undefined;
		reads.value = {};
		saving.value = false;
		resetting.value = false;
		refusal.value = null;
		scope.value = "user";
		selected.value = null;
		showHidden.value = false;
		tab.value = target.tab;
		if (target.tab === "sidebar") sidebar.value = target.address;
		load("user");
	},
	{ immediate: true }
);

watch(tab, () => (selected.value = null));
// A rail edit that stops opening the last sidebar takes its tab away.
// While a read is on its way the draft is empty, which is not an edit.
watch(hasSidebars, (has) => !has && draft.value && (tab.value = "rail"));
watch(sidebar, () => (selected.value = null));
// A selected row that the list now hides leaves the pane for its nearest visible neighbour.
watch(showHidden, (on) => !on && selected.value && leaveIfUnlisted(selected.value));

/** `layout` keeps an edited layout over the fresh read, for a reload that follows a half save. */
async function load(level: Scope, layout?: string): Promise<boolean> {
	const current = opening;
	const ticket = ++newest[level];
	const latest = () => current === opening && ticket === newest[level];
	failed.value = null;
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
		const offered = openedSidebars(read);
		if (!offered.includes(sidebar.value)) sidebar.value = offered[0] ?? "";
		if (tab.value === "sidebar" && !offered.length) tab.value = "rail";
		return true;
	} catch (error) {
		if (latest()) failed.value = (error as Error).message;
		return false;
	}
}

async function switchTo(value: Scope) {
	if (changed.value || value === scope.value) return;
	scope.value = value;
	selected.value = null;
	if (!reads.value[value]) await load(value);
}

function choose(key: string) {
	selected.value = key;
	refusal.value = null;
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

function drop(key: string, before: string) {
	if (draft.value) apply(dropBefore(draft.value, container.value, key, before));
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
	let navigation: Navigation | undefined;
	try {
		const payload = toPayload(before, edited);
		if (Object.keys(payload).length)
			navigation = await saveArrangements(boot.app!, level, payload, read.version);
		if (layoutChanged(before, edited))
			navigation = await saveNavigationLayout(boot.app!, edited.layout, level);
		if (navigation) emit("saved", navigation);
		if (current === opening) emit("close");
	} catch (error) {
		// The shell takes rows that went in, even when the editor was reopened since.
		if (navigation) emit("saved", navigation);
		if (current !== opening) return;
		failed.value = (error as Error).message;
		stale.value = isApiError(error) && !!error.isTimestampMismatch;
		// The rows are in: the next Save needs the version they made.
		if (navigation) await keepSavedRows(level, edited, failed.value, current);
	} finally {
		if (current === opening) saving.value = false;
	}
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
	return row.label || row.link_to || row.key;
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
