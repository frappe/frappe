<!--
  The full-page new record every app gets at /apps/<prefix>/<slug>/new. The address is the key:
  a new doctype or a new query is a new opening, built again from the defaults and the query.
-->
<template>
	<UnsavedRecord
		v-if="doctype"
		:key="openingKey(route)"
		:doctype="doctype"
		:query="route.query"
	/>
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
import { openingKey } from "./record/openingKey";
import PageFrame from "@/shell/PageFrame.vue";
import UnsavedRecord from "./record/UnsavedRecord.vue";

const addresses = inject<Addresses>("addresses")!;
const route = useRoute();
const doctype = computed(() => addresses.doctypeOf(String(route.params.doctype)));
</script>
