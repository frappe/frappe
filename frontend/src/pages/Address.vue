<!--
  The page at a doctype's main list or record address: the page an app declared in its place,
  else the standard one.
-->
<template>
	<component
		:is="replacement.page"
		v-if="replacement"
		:key="replacement.identity"
		v-bind="replacement.props"
	/>
	<component :is="asyncPage(standard)" v-else />
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, inject, type Component } from "vue";
import { useRoute } from "vue-router";
import type { Addresses } from "@/addresses";
import { replacementFor } from "@/contributions/registry";
import type { ReplacementContribution } from "@/contributions/types";

type Loader = () => Promise<unknown>;

const props = defineProps<{
	pageKey: ReplacementContribution["key"];
	standard: Loader;
}>();

const addresses = inject<Addresses>("addresses")!;
const route = useRoute();
const pages = new Map<Loader, Component>();

const replacement = computed(() => {
	const doctype = addresses.doctypeOf(String(route.params.doctype));
	const declared = doctype ? replacementFor(doctype, props.pageKey) : undefined;
	if (!doctype || !declared) return null;

	const name = props.pageKey === "record" ? String(route.params.name) : undefined;
	return {
		page: asyncPage(declared.component),
		props: name === undefined ? { doctype } : { doctype, name },
		identity: `${doctype}/${name ?? ""}`,
	};
});

/** One component per loader, so a new route on the same page does not remount it. */
function asyncPage(loader: Loader) {
	let page = pages.get(loader);
	if (!page) {
		// A module's default export, read as vue-router reads a lazy route component.
		page = defineAsyncComponent(() =>
			loader().then((loaded: any) => (loaded.default ?? loaded) as Component)
		);
		pages.set(loader, page);
	}
	return page;
}
</script>
