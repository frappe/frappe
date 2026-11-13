<!-- Customize's notice on a site layout whose app layout changed since the site copied it. While
     `viewing`, the app layout draws read-only in the canvas's place. -->
<template>
	<div data-app-layout-notice>
		<Alert
			:title="title"
			:primary-action="primary ?? undefined"
			:secondary-action="hasApp && reset ? reset : undefined"
		/>
		<div v-if="viewing && app" class="mt-6" data-app-layout-view>
			<SidePanelCanvas v-if="type === 'Side Panel'" :canvas="app" />
			<QuickEntryCanvas v-else-if="type === 'Quick Entry'" :canvas="app" />
			<CanvasForm v-else :canvas="app" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Alert } from "frappe-ui";
import { __ } from "@/i18n";
import { appLayoutCanvas } from "./appLayout";
import CanvasForm from "./CanvasForm.vue";
import type { DesignCanvas } from "./designCanvas";
import { resetToApp } from "./layoutDialogs";
import { typeLabel } from "./layoutMenu";
import QuickEntryCanvas from "./QuickEntryCanvas.vue";
import SidePanelCanvas from "./SidePanelCanvas.vue";

const props = defineProps<{ canvas: DesignCanvas }>();
const viewing = defineModel<boolean>("viewing", { default: false });

const type = computed(() => props.canvas.openLayout.value.type);
const hasApp = computed(() => Boolean(props.canvas.working.value.layouts[type.value]?.app.length));
const app = computed(() => (viewing.value && hasApp.value ? appLayoutCanvas(props.canvas) : null));

const title = computed(() => {
	const label = typeLabel(type.value);
	if (viewing.value) return __("The app's {0} layout, read-only", [label]);
	if (!hasApp.value) return __("The DocType's fields changed since this site layout was made");
	return __("The app's {0} layout changed since this site layout was made", [label]);
});
const reset = computed(() =>
	props.canvas.editable
		? { label: __("Reset to app layout"), onClick: () => resetToApp(props.canvas, type.value) }
		: null
);
const primary = computed(() => {
	if (!hasApp.value) return reset.value;
	const label = viewing.value ? __("Back to site layout") : __("View app layout");
	return { label, onClick: () => void (viewing.value = !viewing.value) };
});
</script>
