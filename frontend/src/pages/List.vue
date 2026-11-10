<!--
  The generated list page every app gets at /apps/<prefix>/<slug>, and every view of it at
  /view/<key>. The view is the key: another view is another page state. A view opens the page
  the app declared for its type, else the standard one; /view/list is always the standard list.
-->
<template>
	<NotFound v-if="!doctype" />
	<PageFrame v-else-if="viewState" :state="viewState" />
	<PageFrame v-else-if="!opened" :scroll="false" />
	<ViewPage
		v-else
		:key="`${doctype}/${opened.key}/${opened.type}/${opened.layer}`"
		:doctype="doctype"
		:opened="opened"
		:replacement="replacement"
	/>
</template>

<script setup lang="ts">
import { computed, inject, watch } from "vue";
import { useRoute } from "vue-router";
import type { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { replacementFor } from "@/contributions/registry";
import { __ } from "@/i18n";
import { isMissing, useSavedView } from "@/list/savedView";
import { PLAIN_LIST } from "@/list/useListPage";
import { typeKey } from "@/list/view";
import NotFound from "@/shell/NotFound.vue";
import PageFrame from "@/shell/PageFrame.vue";
import { failedState, type PageStateValue } from "@/shell/pageState";
import { recentVisits } from "@/shell/recentVisits";
import ViewPage from "./list/ViewPage.vue";

const addresses = inject<Addresses>("addresses")!;
const boot = inject<Boot>("boot")!;
const route = useRoute();

const doctype = computed(() => addresses.doctypeOf(String(route.params.doctype)));
const key = computed(() => (route.params.key ? String(route.params.key) : null));

const savedView = useSavedView(
	() => doctype.value,
	() => key.value
);

const opened = computed(() => (key.value ? savedView.view.value : PLAIN_LIST));

const viewState = computed((): PageStateValue | null => {
	const failure = savedView.failure.value;
	if (failure && isMissing(failure)) return { name: "viewNotFound", doctype: doctype.value! };
	if (failure) return failedState(failure, savedView.retry);
	if (!opened.value || opened.value.applies) return null;
	return {
		name: "viewNotFound",
		doctype: doctype.value!,
		title: __("{0} views don't apply to {1}", [
			typeLabel(opened.value.type),
			__(doctype.value!),
		]),
		description: __("Open its list, or another view of it."),
	};
});

const replacement = computed(() => {
	if (route.name === "standard-list" || !opened.value) return null;
	return replacementFor(doctype.value!, typeKey(opened.value.type), boot.app)?.component ?? null;
});

function typeLabel(type: string) {
	return __(boot.view_types?.find((one) => one.name === type)?.label ?? type);
}

watch(
	() => savedView.view.value?.label,
	(label) => label && recentVisits.retitle(route.path, label)
);
</script>
