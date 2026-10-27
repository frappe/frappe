<!--
  The generated list page every app gets at /apps/<prefix>/<slug>. The doctype is the key: a
  new doctype is a new list, with its own state and its own controls.
-->
<template>
	<DoctypeList v-if="doctype" :key="doctype" :doctype="doctype" :view="view" />
	<NotFound v-else />
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { useRoute } from "vue-router";
import type { Addresses } from "@/addresses";
import NotFound from "@/shell/NotFound.vue";
import DoctypeList from "./list/DoctypeList.vue";

const addresses = inject<Addresses>("addresses")!;
const route = useRoute();

const doctype = computed(() => addresses.doctypeOf(String(route.params.doctype)));
const view = computed(() => (route.params.viewName ? String(route.params.viewName) : null));
</script>
