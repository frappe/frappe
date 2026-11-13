<!-- The DocType editor at `/doctype/<name>`: one DocType in Design or Customize, with the pending
     edits a save sends. `/doctype/new` asks four questions first and edits a DocType not yet saved. -->
<template>
	<PageFrame :scroll="false" :state="pageState">
		<template v-if="state" #header>
			<EditorHeader
				v-model:tab="tab"
				:doctype="state.doctype"
				:layout-title="layout?.title || __('Details')"
				:dirty="edits.dirty.value"
				:can-undo="edits.canUndo.value"
				:can-redo="edits.canRedo.value"
				:switch-to="switchTo"
				@act="(name) => acts.perform(name)"
			/>
		</template>
		<NewDoctypeDialog
			v-if="asking"
			@create="startNew"
			@cancel="router.push(routeFor('DocType'))"
		/>
		<div
			v-if="!state && !asking"
			class="flex flex-1 items-center justify-center text-base text-ink-gray-5"
		>
			{{ __("Loading {0}…", [name]) }}
		</div>
		<template v-else-if="state">
			<div
				class="flex flex-1 items-center justify-center border-t px-6 text-center text-base text-ink-gray-6 lg:hidden"
			>
				{{ __("The editor needs a wider window, 1024px or more.") }}
			</div>
			<ScrollArea
				class="hidden min-h-0 flex-1 border-t lg:flex"
				:viewport-class="pageGutter"
			>
				<EditorCanvas
					v-if="tab === 'editor'"
					:state="state"
					:layout="layout?.layout ?? []"
					:meta-line="metaLine"
				/>
				<SettingsTab v-else-if="tab === 'settings'" />
				<PreviewTab
					v-else-if="!state.pending"
					:doctype="state.doctype"
					:record="previewName"
					:latest="latest"
					@pick="previewName = $event"
				/>
				<p v-else class="py-6 text-base text-ink-gray-5">
					{{ __("Save the DocType to preview its records.") }}
				</p>
			</ScrollArea>
		</template>
	</PageFrame>
</template>

<script setup lang="ts">
import { computed, reactive, ref, shallowRef, watch } from "vue";
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from "vue-router";
import { ScrollArea } from "frappe-ui";
import { listDocuments } from "@framework/ui/api";
import { acts } from "@/acts/dispatcher";
import { __ } from "@/i18n";
import { discardChanges } from "@/pages/record/discardChanges";
import { routeFor } from "@/router/routeFor";
import { shellDialog } from "@/shell/dialog";
import PageFrame, { pageGutter } from "@/shell/PageFrame.vue";
import { failedState, type PageStateValue } from "@/shell/pageState";
import { useUnloadGuard } from "@/unloadGuard";
import EditorCanvas from "./EditorCanvas.vue";
import EditorHeader from "./EditorHeader.vue";
import { useEditorActs } from "./editorActs";
import {
	detailsLayout,
	loadEditor,
	modeOf,
	pendingDoctype,
	type EditorState,
	type NewDoctype,
} from "./editorSource";
import NewDoctypeDialog from "./NewDoctypeDialog.vue";
import { PendingEdits, type EditorTab, type PendingEditsPayload } from "./pendingEdits";
import PreviewTab from "./PreviewTab.vue";
import SettingsTab from "./SettingsTab.vue";

const route = useRoute();
const router = useRouter();
const name = computed(() => String(route.params.name));

const state = shallowRef<EditorState | null>(null);
const pageState = shallowRef<PageStateValue | null>(null);
const tab = ref<EditorTab>("editor");
const previewName = ref<string | null>(null);
const latest = ref<string[]>([]);
const asking = computed(() => name.value === "new" && !state.value);

// Filled when the load lands; the payload reads it then.
const head = reactive({}) as Omit<PendingEditsPayload, "edits">;
const edits = new PendingEdits(head, (opened) => (tab.value = opened));

useEditorActs({
	edits,
	tab,
	find: () => (tab.value = "editor"),
	previewRecord: (record) => (previewName.value = record),
	recordOptions: async (query) =>
		[null, ...latest.value]
			.filter(
				(record) => !query || (record ?? "").toLowerCase().includes(query.toLowerCase())
			)
			.map((record) => ({ value: record, label: record ?? __("Empty form") })),
});

const layout = computed(() => (state.value ? detailsLayout(state.value) : null));

const metaLine = computed(() => {
	const one = state.value;
	if (!one) return "";
	const parts = [one.module, one.app_title ? __("From {0}", [one.app_title]) : __("Custom")];
	if (one.record_count != null)
		parts.push(__("{0} records", [one.record_count.toLocaleString()]));
	return parts.join(" · ");
});

const switchTo = computed(() => {
	const other = state.value?.modes.find((mode) => mode !== state.value?.mode);
	if (!other) return null;
	const label = other === "Customize" ? __("Customize form") : __("Edit DocType");
	return {
		label,
		onClick: () => router.push({ query: { ...route.query, mode: other.toLowerCase() } }),
	};
});

watch(() => [name.value, route.query.mode], load, { immediate: true });

let loading = 0;

async function load() {
	const request = ++loading;
	reset();
	if (name.value === "new") return;
	try {
		const loaded = await loadEditor(name.value, modeOf(route.query.mode));
		if (request !== loading) return;
		open(loaded);
		loadLatest(loaded, request).catch(() => (latest.value = []));
	} catch (error) {
		if (request === loading) pageState.value = failedState(error, load);
	}
}

function reset() {
	state.value = null;
	pageState.value = null;
	tab.value = "editor";
	latest.value = [];
	previewName.value = null;
	edits.clear();
}

function startNew(answers: NewDoctype) {
	open(pendingDoctype(answers));
}

function open(loaded: EditorState) {
	Object.assign(head, {
		doctype: loaded.doctype,
		mode: loaded.mode,
		base_version: loaded.base_version,
	});
	state.value = loaded;
}

async function loadLatest(loaded: EditorState, request: number) {
	const { issingle, istable } = loaded.definition;
	if (issingle || istable || !loaded.record_count) return;
	const { data } = await listDocuments<{ name: string }>(loaded.doctype, {
		fields: ["name"],
		order_by: "modified desc",
		limit: 20,
	});
	if (request !== loading) return;
	latest.value = data.map((row) => String(row.name));
	previewName.value = latest.value[0] ?? null;
}

async function confirmLeave() {
	if (!edits.dirty.value) return true;
	return discardChanges(
		shellDialog().confirm,
		__("This DocType has changes that are not saved.")
	);
}

onBeforeRouteLeave(confirmLeave);
onBeforeRouteUpdate((to, from) =>
	to.params.name === from.params.name && to.query.mode === from.query.mode
		? true
		: confirmLeave()
);
useUnloadGuard(() => edits.dirty.value);
</script>
