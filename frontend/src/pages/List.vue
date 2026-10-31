<!--
  The generated list page every app gets at /apps/<prefix>/<slug>. The doctype is the key: a
  new doctype is a new list, with its own state and its own controls. A saved view's address
  opens the same page once the view is found.
-->
<template>
	<NotFound v-if="!doctype" />
	<PageFrame v-else-if="viewState" :state="viewState" />
	<PageFrame v-else-if="view && !savedView.view.value" :scroll="false" />
	<DoctypeList
		v-else
		:key="doctype"
		:doctype="doctype"
		:view="view"
		:view-label="savedView.view.value?.label"
	/>
</template>

<script setup lang="ts">
import { computed, inject, watch } from "vue";
import { useRoute } from "vue-router";
import type { Addresses } from "@/addresses";
import { isMissing, useSavedView } from "@/list/savedView";
import NotFound from "@/shell/NotFound.vue";
import PageFrame from "@/shell/PageFrame.vue";
import { failedState } from "@/shell/pageState";
import { recentVisits } from "@/shell/recentVisits";
import DoctypeList from "./list/DoctypeList.vue";

const addresses = inject<Addresses>("addresses")!;
const route = useRoute();

const doctype = computed(() => addresses.doctypeOf(String(route.params.doctype)));
const view = computed(() => (route.params.key ? String(route.params.key) : null));

const savedView = useSavedView(
	() => doctype.value,
	() => view.value
);

const viewState = computed(() => {
	const failure = savedView.failure.value;
	if (!failure) return null;
	if (isMissing(failure)) return { name: "viewNotFound" as const, doctype: doctype.value! };
	return failedState(failure, savedView.retry);
});

watch(
	() => savedView.view.value?.label,
	(label) => label && recentVisits.retitle(route.path, label)
);
</script>
