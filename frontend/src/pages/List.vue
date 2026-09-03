<template>
	<div class="overflow-y-auto p-8">
		<h1 class="text-lg font-semibold">{{ doctype ?? "Unknown" }}</h1>

		<p v-if="!doctype" class="mt-2 text-sm text-ink-gray-6">
			No doctype is served at <code>{{ route.params.doctype }}</code> under this prefix.
		</p>

		<table v-else class="mt-4 w-full max-w-3xl text-sm">
			<tbody>
				<tr v-for="row in rows" :key="row.name" class="border-b border-outline-gray-1">
					<td class="py-1.5">
						<!-- `routeFor`, never a template literal: under a modular prefix the hand-built form
													resolves to the wrong page. -->
						<RouterLink
							:to="routeFor(doctype!, row.name)"
							class="text-ink-blue-3 hover:underline"
						>
							{{ row.name }}
						</RouterLink>
					</td>
					<td v-for="column in columns" :key="column" class="py-1.5 text-ink-gray-7">
						{{ row[column] }}
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, ref, watchEffect } from "vue";
import { RouterLink, useRoute } from "vue-router";
import type { Addresses } from "@/addresses";
import { routeFor } from "@/router/routeFor";
import { listHandlersFor } from "@/contributions/registry";

const addresses = inject<Addresses>("addresses")!;
const route = useRoute();
const rows = ref<Record<string, string>[]>([]);

const doctype = computed(() => addresses.doctypeOf(String(route.params.doctype)));

// A contributed `list.js` is read here and nowhere else; it shapes the view, never adds a route.
const columns = computed(() => {
	if (!doctype.value) return [];
	return listHandlersFor(doctype.value).flatMap(({ handlers }) =>
		(handlers.columns ?? []).map((column) => column.fieldname)
	);
});

// The slower of two in-flight fetches must not repaint the list the reader left.
let generation = 0;

watchEffect(async () => {
	if (!doctype.value) return;
	const mine = ++generation;
	// Cleared before the fetch: the heading switches synchronously. Writing `rows` does not
	// re-trigger this effect, since nothing here reads it.
	rows.value = [];
	const params = new URLSearchParams({
		doctype: doctype.value,
		fields: JSON.stringify(["name", ...columns.value]),
		limit_page_length: "20",
	});
	const res = await fetch(`/api/method/frappe.client.get_list?${params}`);
	const body = res.ok ? (await res.json()).message ?? [] : [];
	if (mine !== generation) return;
	rows.value = body;
});
</script>
