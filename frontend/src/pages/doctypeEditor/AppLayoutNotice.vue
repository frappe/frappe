<!-- Customize's notice on a site layout whose app layout changed since the site copied it. While
     `viewing`, the slot draws the app layout read-only in the canvas's place. -->
<template>
	<div data-app-layout-notice>
		<Alert
			:title="title"
			:primary-action="primary ?? undefined"
			:secondary-action="hasApp && reset ? reset : undefined"
		/>
		<div v-if="viewing && app" class="mt-6" data-app-layout-view>
			<slot :app="app" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, effectScope, onScopeDispose, shallowRef, watch, type EffectScope } from "vue";
import { Alert } from "frappe-ui";
import { __ } from "@/i18n";
import type { DesignCanvas } from "./designCanvas";
import { resetToApp } from "./layoutDialogs";
import { typeLabel } from "./layoutNames";

const props = defineProps<{ canvas: DesignCanvas }>();
const viewing = defineModel<boolean>("viewing", { default: false });
defineSlots<{ default(props: { app: DesignCanvas }): unknown }>();

const type = computed(() => props.canvas.openLayout.value.type);
const hasApp = computed(() => Boolean(props.canvas.working.value.layouts[type.value]?.app.length));
const app = shallowRef<DesignCanvas | null>(null);
let appScope: EffectScope | null = null;
watch(
	[
		viewing,
		hasApp,
		type,
		() => props.canvas.openLayout.value.id,
		() => props.canvas.layout.value?.condition,
	],
	() => {
		appScope?.stop();
		appScope = viewing.value && hasApp.value ? effectScope(true) : null;
		app.value = appScope?.run(() => props.canvas.appView()) ?? null;
	},
	{ immediate: true }
);
onScopeDispose(() => appScope?.stop());

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
