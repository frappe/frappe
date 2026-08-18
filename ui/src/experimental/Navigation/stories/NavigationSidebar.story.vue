<template>
	<div class="flex flex-col gap-4 p-6">
		<div class="flex items-center gap-2">
			<span class="text-p-sm text-ink-gray-6">App</span>
			<Select v-model="app" :options="appOptions" class="w-32" />
			<span class="text-p-sm text-ink-gray-6">Doctype</span>
			<Select v-model="doctype" :options="doctypeOptions" class="w-56" />
		</div>

		<div class="flex gap-6">
			<div class="w-56 rounded border border-outline-gray-2 p-2">
				<NavigationSidebar
					:key="`${app}:${doctype}`"
					:doctype="doctype"
					:app="app"
					:basePath="basePath"
				/>
			</div>

			<div class="flex flex-col gap-1 text-xs text-ink-gray-6">
				<div>manages shared area = {{ navigation.canManageShared.value }}</div>
				<div>hidden items = {{ hiddenLabels.length ? hiddenLabels : "(none)" }}</div>
				<div>active view = {{ navigation.activeView.value?.label ?? "(none)" }}</div>
				<div>filters = {{ views.activeSnapshot.value.filters ?? "(default)" }}</div>
				<div>sort = {{ views.activeSnapshot.value.sort ?? "(default)" }}</div>
				<div>columns = {{ views.activeSnapshot.value.columns ?? "(default)" }}</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import { Select } from "frappe-ui";
import { NavigationSidebar, useNavigation } from "../index";
import { useSavedViews, viewIdFromPath } from "../../SavedViews";

const doctypeOptions = ["CRM Lead", "CRM Deal", "CRM Task", "ToDo"];
const doctype = ref("CRM Deal");
const appOptions = ["crm", "frappe"];
const app = ref("crm");

const route = useRoute();
const basePath = computed(() => route.path.split("/view/")[0]);

const navigation = useNavigation(doctype.value, () => viewIdFromPath(route.path), {
	app: app.value,
});
const views = useSavedViews(doctype.value, {
	app: app.value,
	activeView: navigation.activeView,
});

const hiddenLabels = computed(() =>
	navigation.sections.value
		.flatMap((section) => section.items)
		.filter((item) => item.hidden)
		.map((item) => item.label)
);
</script>
