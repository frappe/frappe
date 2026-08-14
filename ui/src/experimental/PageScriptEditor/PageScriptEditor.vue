<template>
	<div class="flex min-h-0 flex-1 flex-col">
		<!-- One header, and only one (ticket 37, round 14). It holds everything
		     about the open script — where it is, what it is called, whether it
		     runs, whether it is saved, and what you can do to it — and the rail
		     holds everything about the others.

		     It reads as two zones that both carry weight: the trail and the state
		     hard-left, `⋯` `?` `Save` hard-right. That is the decision underneath
		     rounds 10–13, which kept failing on the same thing — the void in the
		     middle was never spacing, it was a right-hand cluster with nothing in
		     it. There is no `×`: Escape, the overlay and Back all still close the
		     dialog. -->
		<div class="flex shrink-0 items-center gap-2 border-b border-outline-gray-1 p-4">
			<PageScriptTrail :doctype="dt" :script="selectedName" @update:doctype="dt = $event" />

			<!-- The rail's dimmed label says *which* scripts are off, but the row
			     you are editing is the selected one, whose label is the least
			     visible thing in the list — so the open script's disabled-ness is
			     stated where its name is (ticket 37, amendment 3). -->
			<Badge
				v-if="selected && !selected.enabled"
				class="ml-1 shrink-0"
				theme="gray"
				variant="outline"
				size="md"
				label="Disabled"
			/>

			<!-- The state reads straight after the trail: it is a fact about what
			     the trail just named. A failure takes the same slot — it is the
			     same question, answered badly. -->
			<ErrorMessage v-if="error" class="ml-1 min-w-0 shrink" :message="error" />
			<Badge
				v-else-if="dirty && !saving"
				class="ml-1 shrink-0"
				theme="amber"
				variant="outline"
				size="md"
				label="Unsaved"
			>
				<!-- Literally the mark a dirty row draws in the rail, so the two
				     placements are one system: this says the editor has an unsaved
				     script, the rail's dot says which ones. -->
				<template #prefix>
					<span class="size-1.5 rounded-full bg-surface-amber-5" aria-hidden="true" />
				</template>
			</Badge>
			<p
				v-else-if="stateText"
				class="ml-1 flex min-w-0 items-center gap-2 text-p-sm text-ink-gray-5"
			>
				<span
					v-if="!saving"
					class="lucide-check size-3.5 shrink-0 text-ink-green-8"
					aria-hidden="true"
				/>
				<span class="truncate">{{ stateText }}</span>
			</p>

			<div class="ml-auto flex shrink-0 items-center gap-1">
				<!-- The open script's own actions, beside everything else about it.
				     The rail's rows keep theirs — a row's `⋯` is the only way to
				     reach a script you have not opened — so this is the same menu
				     addressed to the selected one (ticket 37, amendment 4). -->
				<Dropdown v-if="selected" :options="selectedActions" align="end">
					<Button
						variant="ghost"
						icon="lucide-ellipsis"
						:label="`Actions for ${selected.name}`"
					/>
				</Dropdown>
				<!-- `icon` + `label`, never `iconLeft` + `aria-label`: Button sets
				     `aria-label` from its own `label` last, so a passed one is
				     overwritten, and `icon` is the prop that renders bare and square
				     (ticket 27, then 35). -->
				<Tooltip text="Reference">
					<Button
						variant="ghost"
						icon="lucide-circle-help"
						label="Reference"
						@click="showReference = !showReference"
					/>
				</Tooltip>
				<!-- Save is absent rather than disabled when there is nothing to
				     save (ticket 23), so 'clean' can never be misread as 'cannot
				     save'. Help sits beside the work; the primary action is the
				     last thing on the line. -->
				<Button
					v-if="dirty"
					variant="solid"
					label="Save"
					:loading="saving"
					@click="save"
				/>
			</div>
		</div>

		<!-- The reference covers this, so the three population states share a
		     positioned wrapper: it is the branch set's sibling rather than any one
		     branch's child, which is what makes `?` work in every state including
		     the empty one, and what stops it from drifting back into one of them.
		     The header stays uncovered — `?` is how the reference closes again.

		     It is also where focus starts, and the `[autofocus]` that says so is
		     read by the host as well as by this pane: seeing one, frappe-ui's
		     `Dialog` leaves initial focus alone instead of letting its trap take
		     the first tabbable element — which is now the doctype crumb, a
		     Combobox trigger that would open a picker in the author's face
		     (ticket 36, and 37 flagged the crumb as a new tab stop ahead of the
		     code). -->
		<div
			ref="pane"
			autofocus
			tabindex="-1"
			class="relative flex min-h-0 flex-1 flex-col outline-none"
		>
			<div v-if="loading" class="flex min-h-0 flex-1 flex-col gap-2 p-4">
				<Skeleton class="h-6 w-48" />
				<Skeleton class="min-h-0 w-full flex-1" />
			</div>

			<!-- Zero scripts: no rail, and the pane teaches rather than showing a
			     read-only example (ticket 37, item 3 option D). Focus lands on the
			     first starter — the only thing there is to act on. -->
			<div v-else-if="!scripts.length" autofocus class="flex min-h-0 flex-1 flex-col">
				<PageScriptEmptyState
					:dt="dt"
					:busy="saving"
					@create="startFrom"
					@reference="showReference = true"
				/>
			</div>

			<div v-else class="flex min-h-0 flex-1">
				<PageScriptRail
					:scripts="scripts"
					:selectedName="selectedName"
					:isDirty="isDirty"
					:busy="saving"
					@select="select"
					@create="startFrom()"
					@toggleEnabled="setEnabled($event, !$event.enabled)"
					@duplicate="duplicate"
					@reorder="reorder"
					@remove="confirmRemove"
				/>

				<!-- The editor is the reason the dialog exists, so it takes every
				     pixel the header and rail leave — and, for the same reason, the
				     focus. With the footer gone it runs to the panel's bottom edge. -->
				<div class="flex min-w-0 flex-1 flex-col">
					<div autofocus class="code-fill flex min-h-0 flex-1 flex-col p-4">
						<CodeEditor
							v-model="draft"
							class="min-h-0 flex-1"
							language="javascript"
							:style="{ '--cm-max-height': '100%' }"
							placeholder="export default { refresh(page) {} }"
						/>
						<!-- The import surface is enforced, never stated. Not
						     dismissible: a lint you can dismiss while it is still true
						     is a lint that lies. -->
						<Alert
							v-if="badImports.length"
							class="mt-2 shrink-0"
							theme="red"
							:dismissible="false"
							:title="`'${badImports[0]}' won't resolve at runtime`"
							:description="`Scripts may import ${SHARED_DEPS.join(', ')} — and nothing else, not even a subpath of those.`"
						/>
					</div>
				</div>
			</div>

			<PageScriptReference v-if="showReference" @close="showReference = false" />
		</div>

		<NewPageScriptDialog
			v-model="naming"
			:taken="scripts.map((row) => row.name)"
			:onSubmit="createNamed"
		/>
	</div>
</template>

<script setup lang="ts">
// The generic Page Script editor: one doctype's scripts, listed in run order,
// with the selected one open in a code editor that fills the pane. Saving is all
// it does to the running page — the doctype publishes its change event and any
// mounted Record page replays the tier on its own.
//
// Zero, one and many scripts are three layouts rather than one (ticket 23): the
// same layout lied about two of them.
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
	Alert,
	Badge,
	Button,
	dialog,
	Dropdown,
	ErrorMessage,
	Skeleton,
	Tooltip,
} from "frappe-ui";
import { CodeEditor } from "frappe-ui/code-editor";
import NewPageScriptDialog from "./NewPageScriptDialog.vue";
import PageScriptEmptyState from "./PageScriptEmptyState.vue";
import PageScriptRail from "./PageScriptRail.vue";
import PageScriptReference from "./PageScriptReference.vue";
import PageScriptTrail from "./PageScriptTrail.vue";
import { focusableIn } from "./focusTarget";
import { SHARED_DEPS, unresolvableImports } from "./importLint";
import { rowActions } from "./rowActions";
import { usePageScriptEditor } from "./usePageScriptEditor";
import type { PageScriptDoc } from "./pageScriptApi";

const props = defineProps<{
	/**
	 * The record the author is watching replay behind this editor, if there is
	 * one — it names what a save just took effect on. Absent on the route, which
	 * is opened away from any record, and absent once the doctype being edited
	 * is no longer that record's.
	 */
	replaysOn?: string;
	/**
	 * The record behind the dialog whatever its doctype, so that switching the
	 * doctype can *withdraw* the replay claim rather than silently dropping it
	 * (ticket 37: the line is what keeps the dialog honest about it).
	 */
	record?: string;
}>();

/**
 * The doctype whose Record page scripts these are. A model rather than a prop:
 * the trail's doctype crumb switches it, and the host is what turns that into
 * `#page-scripts/<doctype>` (tickets 31/32).
 */
const dt = defineModel<string>("dt", { required: true });

/** The script a host addresses; it is written back whenever the pane corrects it. */
const boundScript = defineModel<string | undefined>("script", {
	default: undefined,
});

const {
	scripts,
	selected,
	selectedName,
	draft,
	dirty,
	isDirty,
	loading,
	saving,
	error,
	select,
	create,
	duplicate,
	save,
	setEnabled,
	reorder,
	remove,
} = usePageScriptEditor(
	() => dt.value,
	() => boundScript.value,
);

watch(selectedName, (name) => (boundScript.value = name ?? undefined));

const naming = ref(false);
const showReference = ref(false);

// What the empty state's starters carry: the body the new script opens with, so
// the author lands in something that already runs rather than in a blank page.
// It survives the naming dialog, which is what stands between the click and the
// script existing (Page Script is `autoname: prompt`).
const pendingScript = ref<string | undefined>(undefined);

function startFrom(script?: string) {
	pendingScript.value = script;
	naming.value = true;
}

function createNamed(name: string) {
	return create(name, pendingScript.value);
}

const selectedActions = computed(() =>
	selected.value
		? rowActions(
				selected.value,
				{
					toggleEnabled: (row) => setEnabled(row, !row.enabled),
					duplicate,
					remove: confirmRemove,
				},
				saving.value,
			)
		: [],
);

// 23 put code first on screen; the same reasoning puts focus there. Left alone,
// a host's focus trap takes the first tabbable element in its panel, which is
// the header's doctype crumb, and the first keystroke opens a doctype picker.
//
// Two steps, because the editor is not there to be focused when the dialog
// opens: the pane takes focus itself on mount — the marker keeps the host from
// choosing, and `tabindex="-1"` makes a place to park without adding a tab stop
// — and hands it to the layout's own target once the scripts have arrived. The
// host's `[autofocus]` pass (frappe-ui's `useAutofocusOnOpen`) cannot do the
// second step: it runs once, on open, while this pane is still loading.
//
// Which element is the target is the layout's business — the empty state has
// nothing to type into, so its first starter carries the marker instead.
const pane = ref<HTMLElement>();
let focusTaken = false;

onMounted(() => pane.value?.focus());

watch(loading, focusEditor, { immediate: true });

async function focusEditor(isLoading: boolean) {
	if (isLoading || focusTaken) return;
	// Once per mount only. The dialog remounts this pane on every open, so this
	// is once per visit — and a later reload (a delete, a refused reorder) must
	// not yank focus back out of wherever the author has since put it.
	focusTaken = true;
	await nextTick();
	const marker = pane.value?.querySelector<HTMLElement>("[autofocus]");
	if (!marker) return;
	const target = await focusableIn(marker);
	// Not if the author got there first. Anything focused inside the pane by the
	// time the editor arrives is a click, and a click outranks a default — the
	// pane's own parking spot excepted, since that is exactly what this relieves.
	const active = document.activeElement;
	const claimed = active !== pane.value && pane.value?.contains(active);
	if (target?.isConnected && !claimed) target.focus();
}

const badImports = computed(() => unresolvableImports(draft.value));

const stateText = computed(() => {
	if (saving.value) return "Saving…";
	if (!selected.value) return "";
	// A disabled script is saved but replayed nowhere, so it cannot claim a
	// replay — the `Disabled` badge beside this says why, and the line just
	// stops claiming (ticket 37, amendment 3).
	if (!selected.value.enabled) return "Saved · not running";
	if (props.replaysOn) return `Saved · replayed on ${props.replaysOn}`;
	// The claim is only true while the doctype being edited is the record's own.
	// Switching the crumb can put the author on a Deal editing Lead scripts, and
	// watching the record replay is the whole reason this is a dialog — so the
	// line withdraws the claim out loud rather than going quiet.
	if (props.record) return `Saved · not replayed here — you are on ${props.record}`;
	return "Saved";
});

// ⌘S has to be caught on the document too: CodeMirror stops the keydown from
// reaching the pane once focus is inside the editor's own keymap. The header no
// longer says so — `⌘S to save` was instruction where a state line belongs
// (ticket 37, rounds 6, 9 and 11) — but the chord still saves.
onMounted(() => document.addEventListener("keydown", onSaveChord));
onBeforeUnmount(() => document.removeEventListener("keydown", onSaveChord));

function onSaveChord(event: KeyboardEvent) {
	if (event.key !== "s" || !(event.metaKey || event.ctrlKey)) return;
	if (!dirty.value) return;
	event.preventDefault();
	save();
}

// Destructive actions confirm, and the confirmation is frappe-ui's imperative
// danger dialog — the same one `page.dialog.danger` routes to (ticket 17), so a
// script author sees one shape of "are you sure" throughout.
function confirmRemove(row: PageScriptDoc) {
	dialog.danger({
		title: `Delete ${row.name}?`,
		message: "The script stops running everywhere. This cannot be undone.",
		actions: [
			{
				label: "Delete",
				theme: "red",
				variant: "solid",
				// A failure is reported on the pane behind the dialog, which this
				// would otherwise cover — so the dialog closes either way.
				onClick: () => remove(row),
			},
		],
	});
}
</script>

<style scoped>
/* CodeEditor publishes only `--cm-max-height`, which caps rather than stretches,
   so the CodeMirror root inside it needs a height of its own to fill the column.
   The selector hangs off this template's own wrapper, not off a class handed to
   CodeEditor: its root renders through `LabelingWrapper`, whose fragment root
   never receives this component's scope id, so a scoped rule written against a
   class passed to CodeEditor silently matches nothing. */
.code-fill :deep(.cm-editor) {
	height: 100%;
}
</style>
