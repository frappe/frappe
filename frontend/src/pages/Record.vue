<!--
  The generated record page: what every app gets at /apps/<prefix>/<slug>/<name> with
  no declaration at all. Charter item 2's "default first" made literal.

  Deliberately a MINIMAL host: no form layout, no tabs, no panel. What it proves here is
  that the generated route resolves, the doctype de-slugs through boot, and the record
  loads. Making a contributed `record.js` actually *run* rather than merely be discovered
  is the record-page engine's job and arrives with it.

  What it is NOT is a port of `crm/frontend2`'s record page. That is 1,962 lines across
  a dozen components plus a 400-line composable, and migrating it wholesale is a later
  map. The skeleton's job is to prove the seam carries a contribution end to end.
-->
<template>
	<div class="overflow-y-auto p-8">
		<p v-if="!doctype" class="text-sm text-ink-gray-6">
			No doctype is served at <code>{{ route.params.doctype }}</code> under this prefix.
		</p>

		<template v-else>
			<header class="flex items-center gap-3">
				<h1 class="text-lg font-semibold">{{ route.params.name }}</h1>
				<span class="text-sm text-ink-gray-5">{{ doctype }}</span>
			</header>

			<p v-if="error" class="mt-4 text-sm text-ink-red-4">{{ error }}</p>

			<dl v-else class="mt-6 grid max-w-2xl grid-cols-[12rem_1fr] gap-y-1.5 text-sm">
				<template v-for="[field, value] in fields" :key="field">
					<dt class="text-ink-gray-6">{{ field }}</dt>
					<dd class="text-ink-gray-8">{{ value }}</dd>
				</template>
			</dl>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, ref, watch } from "vue";
import { useRoute } from "vue-router";
import type { Boot } from "@/boot";
import { resolveDoctype } from "@/router";

const boot = inject<Boot>("boot")!;
const route = useRoute();

const doc = ref<Record<string, any>>({});
const error = ref("");

// Which load is current. Navigating A -> B leaves A's fetch in flight, and without
// this the slower response wins: `doc` would hold A while the URL says B.
let generation = 0;

const doctype = computed(() => resolveDoctype(boot, String(route.params.doctype)));
const docname = computed(() => String(route.params.name));

const fields = computed(() =>
	Object.entries(doc.value ?? {})
		.filter(([key]) => !key.startsWith("_") && key !== "doctype")
		.slice(0, 25)
);

async function call(method: string, params: Record<string, string>) {
	const res = await fetch(`/api/method/${method}?${new URLSearchParams(params)}`);
	if (!res.ok) throw new Error(String(res.status));
	return (await res.json()).message;
}

async function load() {
	if (!doctype.value) return;
	const mine = ++generation;
	error.value = "";
	// Blank the record before fetching the next one. `generation` already stops a slow
	// response from repainting the record the reader left, but it says nothing about
	// what is on screen MEANWHILE: the heading reads `route.params.name`, which changes
	// synchronously, so without this the new record's name sits above the old record's
	// field values. On a record page that is not a cosmetic flicker -- it is one
	// record's data presented as another's.
	doc.value = {};
	try {
		const document = await call("frappe.client.get", {
			doctype: doctype.value,
			name: docname.value,
		});
		if (mine !== generation) return;
		doc.value = document;
	} catch (e) {
		if (mine !== generation) return;
		error.value =
			String(e) === "Error: 403"
				? "You do not have permission to read this record."
				: "Not found.";
	}
}

watch([doctype, docname], load, { immediate: true });
</script>
