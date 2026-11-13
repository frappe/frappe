<!-- The DocType editor at `/doctype/<name>`: one DocType in Design or Customize, with the pending
     edits a save sends. `/doctype/new` asks four questions first and edits a DocType not yet saved. -->
<template>
	<PageFrame :scroll="false" :state="pageState">
		<template v-if="state" #header>
			<EditorHeader
				v-model:tab="tab"
				:doctype="state.doctype"
				:layout-title="layout?.title || __('Details')"
				:dirty="dirty"
				:can-undo="edits.canUndo.value"
				:can-redo="edits.canRedo.value"
				:switch-to="switchTo"
				@act="(name) => acts.perform(name)"
			/>
		</template>
		<NewDoctypeDialog
			v-if="asking"
			:initial="asking.answers"
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
					v-if="tab === 'editor' && canvas"
					:canvas="canvas"
					:meta-line="metaLine"
					:customize="customizeRoute"
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
import { ScrollArea, toast } from "frappe-ui";
import { listDocuments } from "@framework/ui/api";
import { acts } from "@/acts/dispatcher";
import { __, __n } from "@/i18n";
import { COPY_OF } from "@/newRecordValues";
import { discardChanges } from "@/pages/record/discardChanges";
import { errorMessage } from "@/recordPage/errorMessage";
import { routeFor } from "@/router/routeFor";
import { shellDialog } from "@/shell/dialog";
import PageFrame, { pageGutter } from "@/shell/PageFrame.vue";
import { failedState, type PageStateValue } from "@/shell/pageState";
import { useUnloadGuard } from "@/unloadGuard";
import EditorCanvas from "./EditorCanvas.vue";
import EditorHeader from "./EditorHeader.vue";
import { DesignCanvas } from "./designCanvas";
import { useEditorActs } from "./editorActs";
import {
	carriedAnswers,
	copiedAnswers,
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
const canvas = shallowRef<DesignCanvas | null>(null);
const pageState = shallowRef<PageStateValue | null>(null);
const tab = ref<EditorTab>("editor");
const previewName = ref<string | null>(null);
const latest = ref<string[]>([]);
// `/doctype/new`'s first answers, once a duplicate's source has loaded.
const starting = shallowRef<{ answers: Partial<NewDoctype>; source: EditorState | null } | null>(
	null
);
const asking = computed(() => (name.value === "new" && !state.value ? starting.value : null));

// Filled when the load lands; the payload reads it then.
const head = reactive({}) as Omit<PendingEditsPayload, "edits">;
const edits = new PendingEdits(head, (opened) => (tab.value = opened));

useEditorActs({
	edits,
	tab,
	canvas: () => canvas.value,
	find,
	previewRecord: (record) => (previewName.value = record),
	recordOptions: async (query) =>
		[null, ...latest.value]
			.filter(
				(record) => !query || (record ?? "").toLowerCase().includes(query.toLowerCase())
			)
			.map((record) => ({ value: record, label: record ?? __("Empty form") })),
});

const layout = computed(() => (state.value ? detailsLayout(state.value) : null));
// A new DocType is not saved until its first save, even with no edits staged.
const dirty = computed(() => edits.dirty.value || Boolean(state.value?.pending));

const metaLine = computed(() => {
	const one = state.value;
	if (!one) return "";
	const parts = [one.module, one.app_title ? __("From {0}", [one.app_title]) : __("Custom")];
	if (one.record_count != null)
		parts.push(
			__n("{0} record", "{0} records", one.record_count, [one.record_count.toLocaleString()])
		);
	return parts.join(" · ");
});

const customizeRoute = computed(() =>
	state.value?.modes.includes("Customize")
		? { query: { ...route.query, mode: "customize" } }
		: null
);

const switchTo = computed(() => {
	const other = state.value?.modes.find((mode) => mode !== state.value?.mode);
	if (!other) return null;
	const label = other === "Customize" ? __("Customize form") : __("Edit DocType");
	return {
		label,
		onClick: () => router.push({ query: { ...route.query, mode: other.toLowerCase() } }),
	};
});

let loading = 0;
watch(() => [name.value, route.query.mode, route.query[COPY_OF]], load, { immediate: true });

async function load() {
	const request = ++loading;
	reset();
	if (name.value === "new") return void startAsking(request);
	try {
		const loaded = await loadEditor(name.value, modeOf(route.query.mode));
		if (request !== loading) return;
		open(loaded);
		loadLatest(loaded, request).catch(() => (latest.value = []));
	} catch (error) {
		if (request === loading) pageState.value = failedState(error, load);
	}
}

async function startAsking(request: number) {
	const { answers, copyOf } = carriedAnswers(route.query);
	let source: EditorState | null = null;
	if (copyOf) {
		try {
			source = await loadEditor(copyOf, "Design");
		} catch (error) {
			toast.error(errorMessage(error));
		}
	}
	if (request !== loading) return;
	starting.value = { answers: { ...(source && copiedAnswers(source)), ...answers }, source };
}

function reset() {
	state.value = null;
	canvas.value = null;
	starting.value = null;
	pageState.value = null;
	tab.value = "editor";
	latest.value = [];
	previewName.value = null;
	edits.clear();
}

function startNew(answers: NewDoctype) {
	open(pendingDoctype(answers, starting.value?.source));
}

function open(loaded: EditorState) {
	Object.assign(head, {
		doctype: loaded.doctype,
		mode: loaded.mode,
		base_version: loaded.base_version,
	});
	state.value = loaded;
	canvas.value = new DesignCanvas(loaded, edits);
}

function find(fieldname: string) {
	tab.value = "editor";
	const open = canvas.value;
	if (!open) return;
	open.select({ kind: "field", fieldname });
	if (!open.place(fieldname)) open.trayOpen.value = true;
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
	if (!dirty.value) return true;
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
useUnloadGuard(() => dirty.value);
</script>
