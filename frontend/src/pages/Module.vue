<!--
  A module's landing page -- framework-generated, and reachable only under a prefix
  whose app declares `app_modular`.

  It exists because an addressable level that 404s is a navigation dead end. A reader
  who deletes the tail of `/apps/erpnext/accounts/sales-invoice/SI-001` expects to
  land somewhere, and now does, all the way up: record, module, app, /apps (#42211 §6).

  PERMISSION-FILTERED, and that is the line #42210 drew held exactly: addressability
  is permission-independent, navigation is filtered. Nobody pastes a module page as a
  record link, so filtering it changes no address's shape.
-->
<template>
	<div class="overflow-y-auto p-8">
		<h1 class="text-xl font-semibold">{{ title }}</h1>
		<p class="mt-1 text-sm text-ink-gray-6">
			<!-- "0 doctypes you can read" is a real answer for a module you can read
					 nothing in, so it must not also be what a pending fetch looks like. -->
			<template v-if="loading">Loading…</template>
			<template v-else>
				{{ entries.length }} doctype{{ entries.length === 1 ? "" : "s" }} you can read.
			</template>
		</p>

		<ul class="mt-6 grid max-w-2xl grid-cols-2 gap-2">
			<li v-for="entry in entries" :key="entry.doctype">
				<RouterLink
					:to="routeFor(entry.doctype)"
					class="block rounded border border-outline-gray-2 px-3 py-2 text-sm hover:bg-surface-gray-2"
				>
					{{ entry.doctype }}
				</RouterLink>
			</li>
		</ul>
	</div>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import { RouterLink, useRoute } from "vue-router";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";
import { routeFor } from "@/router/routeFor";
import { useNavigation } from "@/navigation";

const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;
const route = useRoute();

const moduleSlug = computed(() => String(route.params.module ?? ""));
const { entries, loading } = useNavigation(boot.app, moduleSlug);
// The slug is the address; the name is what a human reads. The server sends both, so
// neither side has to guess the other.
const title = computed(() => addresses.moduleName(moduleSlug.value) ?? moduleSlug.value);
</script>
