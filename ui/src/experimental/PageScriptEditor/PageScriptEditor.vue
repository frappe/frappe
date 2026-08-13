<template>
	<div class="flex min-h-0 flex-1 flex-col">
		<!-- One header, not two (ticket 23). The pane's old header row said the
		     script's name, its run position and its enabled-ness, all of which the
		     rail already says; what is left is the doctype and the way to the
		     reference. -->
		<div class="flex items-center gap-2 border-b border-outline-gray-1 px-4 py-3">
			<span class="text-lg font-semibold text-ink-gray-9">Page scripts</span>
			<span class="text-lg text-ink-gray-4">·</span>
			<span class="text-lg text-ink-gray-6">{{ dt }}</span>
			<!-- `icon` + `label`, never `iconLeft` + `aria-label`: Button sets
			     `aria-label` from its own `label` last, so a passed one is
			     overwritten, and `icon` is the prop that renders bare
			     (ticket 27, then 35). -->
			<div class="ml-auto flex items-center gap-1">
				<Tooltip text="Reference">
					<Button
						variant="ghost"
						icon="lucide-circle-help"
						label="Reference"
						@click="showReference = !showReference"
					/>
				</Tooltip>
				<Button
					v-if="onClose"
					variant="ghost"
					icon="lucide-x"
					label="Close"
					@click="onClose"
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
		     the first tabbable element, which is the header's `?` — and a `?`
		     focused is a black `Reference` tooltip in the author's face, because a
		     tooltip opens instantly for focus rather than after the hover delay. -->
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

			<!-- Zero scripts: no rail, because a list with nothing in it explains
			     nothing. The example fills the editor's slot as a read-only editor —
			     syntax-coloured, so it looks like the thing it teaches — and the
			     primary action takes the footer slot Save occupies later, so the
			     action never moves when the column arrives beside it. -->
			<div v-else-if="!scripts.length" class="flex min-h-0 flex-1 flex-col">
				<div class="code-fill flex min-h-0 flex-1 flex-col p-4">
					<CodeEditor
						class="min-h-0 flex-1"
						:modelValue="EXAMPLE_SCRIPT"
						language="javascript"
						disabled
						:style="{ '--cm-max-height': '100%' }"
					/>
				</div>
				<div class="flex items-center gap-3 border-t border-outline-gray-1 px-4 py-3">
					<ErrorMessage v-if="error" :message="error" />
					<p v-else class="text-p-sm text-ink-gray-5">
						Nothing customizes {{ dt }} record pages yet — this is an example, and it
						neither saves nor runs.
					</p>
					<!-- Focus lands here in this state: the editor beside it is the
					     read-only example, so the only thing to type into is the one
					     this button opens. -->
					<Button
						class="ml-auto"
						autofocus
						variant="solid"
						iconLeft="lucide-plus"
						label="New script"
						:disabled="saving"
						@click="naming = true"
					/>
				</div>
			</div>

			<div v-else class="flex min-h-0 flex-1">
				<PageScriptRail
					:scripts="scripts"
					:selectedName="selectedName"
					:isDirty="isDirty"
					:busy="saving"
					@select="select"
					@create="naming = true"
					@toggleEnabled="setEnabled($event, !$event.enabled)"
					@duplicate="duplicate"
					@reorder="reorder"
					@remove="confirmRemove"
				/>

				<!-- The editor is the reason the dialog exists, so it takes every
				     pixel the header, rail and footer leave — and, for the same
				     reason, the focus. -->
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

					<!-- The footer reports the loop, not the button's own health: Save
					     is absent rather than disabled when there is nothing to save,
					     so 'clean' can never be misread as 'cannot save'. -->
					<div class="flex items-center gap-3 border-t border-outline-gray-1 px-4 py-3">
						<ErrorMessage v-if="error" :message="error" />
						<p v-else class="flex items-center gap-2 text-p-sm" :class="stateClass">
							<span v-if="dirty" class="size-1.5 rounded-full bg-surface-amber-5" />
							<span>{{ stateText }}</span>
						</p>
						<Button
							v-if="dirty"
							class="ml-auto"
							variant="solid"
							label="Save"
							:loading="saving"
							@click="save"
						/>
					</div>
				</div>
			</div>

			<PageScriptReference v-if="showReference" @close="showReference = false" />
		</div>

		<NewPageScriptDialog
			v-model="naming"
			:taken="scripts.map((row) => row.name)"
			:onSubmit="create"
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
import { Alert, Button, dialog, ErrorMessage, Skeleton, Tooltip } from "frappe-ui";
import { CodeEditor } from "frappe-ui/code-editor";
import NewPageScriptDialog from "./NewPageScriptDialog.vue";
import PageScriptRail from "./PageScriptRail.vue";
import PageScriptReference from "./PageScriptReference.vue";
import { EXAMPLE_SCRIPT } from "./exampleScript";
import { focusableIn } from "./focusTarget";
import { SHARED_DEPS, unresolvableImports } from "./importLint";
import { usePageScriptEditor } from "./usePageScriptEditor";
import type { PageScriptDoc } from "./pageScriptApi";

const props = defineProps<{
	/** The doctype whose Record page scripts these are. */
	dt: string;
	/**
	 * The record the author is watching replay behind this editor, if there is
	 * one — it names what a save just took effect on. Absent on the route, which
	 * is opened away from any record.
	 */
	replaysOn?: string;
	/** Renders the close button, for a host that can dismiss the pane. */
	onClose?: () => void;
}>();

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
	() => props.dt,
	() => boundScript.value,
);

watch(selectedName, (name) => (boundScript.value = name ?? undefined));

const naming = ref(false);
const showReference = ref(false);

// 23 put code first on screen; the same reasoning puts focus there. Left alone,
// a host's focus trap takes the first tabbable element in its panel, which is
// the header's `?`, and the first keystroke goes nowhere near the code.
//
// Two steps, because the editor is not there to be focused when the dialog
// opens: the pane takes focus itself on mount — the marker keeps the host from
// choosing, and `tabindex="-1"` makes a place to park without adding a tab stop
// — and hands it to the layout's own target once the scripts have arrived. The
// host's `[autofocus]` pass (frappe-ui's `useAutofocusOnOpen`) cannot do the
// second step: it runs once, on open, while this pane is still loading.
//
// Which element is the target is the layout's business — the read-only example
// state has nothing to type into, so its `New script` carries the marker
// instead.
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
	if (dirty.value) return `Unsaved changes · ${saveChord} to save`;
	if (!selected.value) return "";
	return props.replaysOn ? `Saved · replayed on ${props.replaysOn}` : "Saved";
});

const stateClass = computed(() => (dirty.value ? "text-ink-gray-7" : "text-ink-gray-5"));

// ⌘S has to be caught on the document too: CodeMirror stops the keydown from
// reaching the pane once focus is inside the editor's own keymap.
const saveChord = navigator.platform.includes("Mac") ? "⌘S" : "Ctrl+S";

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
