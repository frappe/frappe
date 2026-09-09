<!--
  The generated list page every app gets at /apps/<prefix>/<slug>. The doctype is the key: a
  new doctype is a new list, with its own state and its own controls.
-->
<template>
	<DoctypeList v-if="doctype" :key="doctype" :doctype="doctype" />
	<PageFrame v-else title="Unknown">
		<p class="py-5 text-sm text-ink-gray-6">
			No doctype is served at <code>{{ route.params.doctype }}</code> under this prefix.
		</p>
	</PageFrame>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { useRoute } from "vue-router";
import type { Addresses } from "@/addresses";
import PageFrame from "@/shell/PageFrame.vue";
import DoctypeList from "./list/DoctypeList.vue";

const addresses = inject<Addresses>("addresses")!;
const route = useRoute();

const doctype = computed(() => addresses.doctypeOf(String(route.params.doctype)));
</script>
