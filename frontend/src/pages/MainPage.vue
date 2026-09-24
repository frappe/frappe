<!--
  The page at a doctype's main list or record address: the page an app declared in its place,
  else the standard one.
-->
<template>
	<component
		:is="loadedPage(page.loader)"
		v-if="page?.props"
		:key="`${page.props.doctype}/${page.props.name ?? ''}`"
		v-bind="page.props"
	/>
	<component :is="loadedPage(page.loader)" v-else-if="page" />
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { useRoute } from "vue-router";
import type { Addresses } from "@/addresses";
import { loadedPage, mainPageFor } from "@/router/mainPage";

const addresses = inject<Addresses>("addresses")!;
const route = useRoute();
const page = computed(() => mainPageFor(route, addresses));
</script>
