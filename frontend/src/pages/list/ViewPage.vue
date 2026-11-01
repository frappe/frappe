<!--
  One view of a doctype: the page state its address opens, laid out by the list page, or handed to
  the page an app declared for the view's type.
-->
<template>
	<component
		:is="loadedPage(replacement)"
		v-if="replacement"
		:doctype="doctype"
		:view="page.view"
	/>
	<ListPage v-else :page="page" :label="opened.label" />
</template>

<script setup lang="ts">
import { useListPage } from "@/list/useListPage";
import type { SavedView } from "@/list/savedView";
import { loadedPage } from "@/router/mainPage";
import ListPage from "./ListPage.vue";

const props = defineProps<{
	doctype: string;
	opened: SavedView;
	replacement?: (() => Promise<unknown>) | null;
}>();

const page = useListPage(props.doctype, props.opened);
</script>
