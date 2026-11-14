<!-- The canvas of the open layout. Details and New record draw at the record page's form width,
     the Details tray under them; Side panel and Quick entry draw in their own frame. -->
<template>
	<div
		class="mx-auto w-full max-w-3xl px-[--page-gutter] pb-[40vh] pt-6"
		data-editor-canvas
		@click="acts.perform('canvas.select', null)"
	>
		<SaveBanner :save="save" :doctype="canvas.state.doctype" />
		<template v-if="formPage">
			<h1 class="text-xl font-semibold text-ink-gray-9">{{ canvas.state.doctype }}</h1>
			<DoctypeDescription :canvas="canvas" />
			<p class="mt-1 text-p-sm text-ink-gray-5" data-editor-meta>
				<Tooltip
					:text="__('Your changes stay on this site and survive its updates')"
					:disabled="!canvas.customize || !canvas.state.app_title"
				>
					<span>{{ metaLine }}</span>
				</Tooltip>
			</p>
			<p v-if="siteFields" class="mt-1 text-p-sm text-ink-gray-5" data-editor-site-fields>
				{{
					__n(
						"{0} field added on this site, edit it in",
						"{0} fields added on this site, edit them in",
						siteFields,
						[siteFields]
					)
				}}
				<RouterLink
					v-if="customize"
					:to="customize"
					class="text-ink-gray-7 underline-offset-2 hover:underline"
					>{{ __("Customize") }} ↗</RouterLink
				>
				<template v-else>{{ __("Customize") }}</template>
			</p>
			<p
				v-if="canvas.newRecordUsesDetails.value"
				class="mt-1 text-p-sm text-ink-gray-5"
				data-new-record-note
			>
				{{ __("New record uses the Details layout") }}
			</p>
		</template>

		<AppLayoutNotice
			v-if="appChanged"
			v-model:viewing="viewingApp"
			:class="formPage ? 'mt-6' : 'mb-6'"
			:canvas="canvas"
		>
			<template #default="{ app }">
				<SidePanelCanvas v-if="type === 'Side Panel'" :canvas="app" />
				<QuickEntryCanvas v-else-if="type === 'Quick Entry'" :canvas="app" />
				<CanvasForm v-else :canvas="app" />
			</template>
		</AppLayoutNotice>
		<template v-if="!showsApp">
			<SidePanelCanvas v-if="type === 'Side Panel'" :canvas="canvas" />
			<QuickEntryCanvas v-else-if="type === 'Quick Entry'" :canvas="canvas" />
			<div v-else class="mt-6"><CanvasForm :canvas="canvas" /></div>

			<OffLayoutTray v-if="type === 'Details' || !canvas.editable" :canvas="canvas" />
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, ref, watch } from "vue";
import { RouterLink, type RouteLocationRaw } from "vue-router";
import { Tooltip, useKeyboardShortcut } from "frappe-ui";
import { acts } from "@/acts/dispatcher";
import { __, __n } from "@/i18n";
import CanvasForm from "./CanvasForm.vue";
import { canvasMove, type Direction } from "./canvasMoves";
import type { DesignCanvas } from "./designCanvas";
import DoctypeDescription from "./DoctypeDescription.vue";
import type { EditorSave } from "./editorSave";
import { provideInertForm } from "./inertForm";
import { takeOff, takesOff } from "./fieldPanel";
import OffLayoutTray from "./OffLayoutTray.vue";
import QuickEntryCanvas from "./QuickEntryCanvas.vue";
import SaveBanner from "./SaveBanner.vue";
import SidePanelCanvas from "./SidePanelCanvas.vue";

const AppLayoutNotice = defineAsyncComponent(() => import("./AppLayoutNotice.vue"));

const props = defineProps<{
	canvas: DesignCanvas;
	save: EditorSave;
	/** Customize mode of this DocType, when the person may open it. */
	customize: RouteLocationRaw | null;
}>();

provideInertForm();

const type = computed(() => props.canvas.openLayout.value.type);
const appChanged = computed(() =>
	Boolean(props.canvas.customize && props.canvas.layout.value?.sourceChanged)
);
const viewingApp = ref(false);
watch([() => props.canvas, () => props.canvas.openLayout.value, appChanged], () => {
	viewingApp.value = false;
});
const showsApp = computed(() => appChanged.value && viewingApp.value);
const editing = () => props.canvas.editable && !showsApp.value;
const formPage = computed(() => type.value === "Details" || type.value === "New Record");
const metaLine = computed(() => {
	const { module, app_title, record_count } = props.canvas.state;
	const parts = [module, app_title ? __("From {0}", [app_title]) : __("Custom")];
	if (record_count != null)
		parts.push(
			__n("{0} record", "{0} records", record_count, [record_count.toLocaleString()])
		);
	return parts.join(" · ");
});
const siteFields = computed(() =>
	props.canvas.state.mode === "Design" ? props.canvas.state.site_custom_fields ?? 0 : 0
);

const ARROWS: [string, Direction][] = [
	["Alt+ArrowUp", "up"],
	["Alt+ArrowDown", "down"],
	["Alt+ArrowLeft", "left"],
	["Alt+ArrowRight", "right"],
];
for (const [combo, direction] of ARROWS) {
	useKeyboardShortcut({
		combo: combo as never,
		description: __("Move the selected item"),
		group: __("Editor"),
		enabled: () => editing() && Boolean(props.canvas.selection.value),
		handler: () => move(direction),
	});
}
useKeyboardShortcut({
	combo: "Slash",
	description: __("Add field"),
	group: __("Editor"),
	enabled: editing,
	handler: () => void acts.perform("fields.add_field"),
});

useKeyboardShortcut({
	combo: "Delete",
	description: __("Take the selected field off this layout"),
	group: __("Editor"),
	enabled: () => Boolean(placedSelection()),
	handler: () => void takeOff(props.canvas, placedSelection()!),
});

/** The selected field, when Delete takes it off the open layout. */
function placedSelection(): string | null {
	const { canvas } = props;
	const selection = canvas.selection.value;
	if (!editing() || !takesOff(canvas) || selection?.kind !== "field") return null;
	return canvas.place(selection.fieldname) ? selection.fieldname : null;
}

function move(direction: Direction) {
	const selection = props.canvas.selection.value;
	const found = selection && canvasMove(props.canvas.tabs.value, selection, direction);
	if (found) void acts.perform(found.act, found.value);
}

watch(
	() => props.canvas.selection.value,
	async () => {
		await nextTick();
		document
			.querySelector("[data-editor-canvas] [data-canvas-selected]")
			?.scrollIntoView({ block: "nearest" });
	}
);
</script>

<style>
/* Specific enough to win over the dragged item's own utilities, hover variants included. */
[data-doctype-editor] .sortable-chosen.canvas-drop-line {
	height: 2px;
	min-height: 0;
	margin: -9px 0;
	padding: 0;
	border: 0;
	border-radius: 1px;
	overflow: hidden;
	box-shadow: none;
	background-color: var(--outline-gray-4);
	opacity: 1;
}
[data-doctype-editor] .sortable-chosen.canvas-drop-line > * {
	display: none;
}
[data-doctype-editor] [data-canvas-empty] > .sortable-chosen.canvas-drop-line {
	margin: 29px 0 0;
}
[data-doctype-editor] [data-canvas-tray-list] > .sortable-chosen.canvas-drop-line {
	margin: 0;
}
[data-doctype-editor] .canvas-tab-drop > .sortable-chosen.canvas-drop-line {
	display: none;
}
.canvas-tab-drop:has(> .canvas-drop-line) {
	background-color: var(--surface-gray-2);
}
</style>
