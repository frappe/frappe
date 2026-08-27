<!--
  The generated record page: what every app gets at /apps/<prefix>/<slug>/<name> with
  no declaration at all. Charter item 2's "default first" made literal.

  It hosts the REAL record-page engine (`createRecordPage`), which is what makes a
  contributed `record.js` run rather than merely be discovered. Deliberately a MINIMAL
  host: no form layout, no tabs, no panel. `RecordPageHost` documents `formLayout` and
  friends as "absent for a host that renders no form", so this is a supported shape
  rather than a fork of the engine.

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

				<!-- Contributed quick actions, in the run order the registry decided. -->
				<div class="ml-auto flex gap-2">
					<Button
						v-for="action in quickActions"
						:key="action.name"
						:label="action.label"
						@click="runAction(action)"
					/>
				</div>
			</header>

			<p v-if="actionError" class="mt-4 text-sm text-ink-red-4">{{ actionError }}</p>
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
import { computed, inject, ref, shallowRef, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Button } from "frappe-ui";
import { createRecordPage, type RecordPageController } from "@framework/ui/experimental";
import type { Boot } from "@/boot";
import { resolveDoctype } from "@/router";

const boot = inject<Boot>("boot")!;
const route = useRoute();
const router = useRouter();

const doc = ref<Record<string, any>>({});
const saved = ref<Record<string, any>>({});
const meta = ref<any>(null);
const error = ref("");
// Kept apart from `error`: a failed ACTION must not blank the record the reader is
// looking at, which sharing one ref would do (the field list renders in its v-else).
const actionError = ref("");
const controller = shallowRef<RecordPageController | null>(null);
const actionsVersion = ref(0);

// Which load is current. Navigating A -> B leaves A's fetch in flight, and without
// this the slower response wins: `doc` would hold A while the URL says B, and `save()`
// would then POST A's fields -- writing the record the user is not looking at.
let generation = 0;

const doctype = computed(() => resolveDoctype(boot, String(route.params.doctype)));
const docname = computed(() => String(route.params.name));

const fields = computed(() =>
	Object.entries(doc.value ?? {})
		.filter(([key]) => !key.startsWith("_") && key !== "doctype")
		.slice(0, 25)
);

const quickActions = computed(() => {
	actionsVersion.value; // re-read after each replay
	return controller.value?.quickActions.visible() ?? [];
});

async function call(method: string, params: Record<string, string>) {
	const res = await fetch(`/api/method/${method}?${new URLSearchParams(params)}`);
	if (!res.ok) throw new Error(String(res.status));
	return (await res.json()).message;
}

async function load() {
	if (!doctype.value) return;
	const mine = ++generation;
	const target = { doctype: doctype.value, name: docname.value };
	error.value = "";
	const carriedActionError = actionError.value;
	try {
		const [document, metadata] = await Promise.all([
			call("frappe.client.get", { doctype: doctype.value, name: docname.value }),
			call("frappe.desk.form.load.getdoctype", { doctype: doctype.value, with_parent: "1" }),
		]);
		if (mine !== generation) return;
		saved.value = { ...document };
		doc.value = JSON.parse(JSON.stringify(document));
		meta.value =
			(metadata?.docs ?? []).find((entry: any) => entry.name === target.doctype) ?? null;
	} catch (e) {
		if (mine !== generation) return;
		error.value =
			String(e) === "Error: 403"
				? "You do not have permission to read this record."
				: "Not found.";
		return;
	}

	controller.value = createRecordPage({
		doctype: target.doctype,
		docname: target.name,
		doc,
		saved,
		meta,
		perms: () => ({}),
		isDirty: () => JSON.stringify(doc.value) !== JSON.stringify(saved.value),
		// No strip on this page, so the reader is never on a tab and activation is a
		// no-op. The engine already refuses to activate a tab it cannot see.
		activeTab: () => "",
		activateTab: () => {},
		save,
		reload: load,
		router,
	});

	await controller.value.refresh();
	if (mine !== generation) return;
	// A reload triggered by a failed action must not wipe the message explaining it.
	actionError.value = carriedActionError;
	actionsVersion.value++;
}

async function save() {
	// Refuse rather than write the wrong record: if the route moved while an action was
	// running, the draft in `doc` no longer belongs to what the URL addresses.
	if (doc.value.name !== docname.value || doctype.value === null) {
		throw new Error("The record changed while saving; nothing was written.");
	}

	const mine = generation;
	const res = await fetch("/api/method/frappe.client.save", {
		method: "POST",
		headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": boot.csrf_token },
		body: JSON.stringify({ doc: { ...doc.value, doctype: doctype.value } }),
	});
	if (!res.ok) throw new Error(`Save failed with ${res.status}`);

	const document = (await res.json()).message;
	if (mine !== generation) return;
	saved.value = { ...document };
	doc.value = JSON.parse(JSON.stringify(document));
	await controller.value?.refresh();
	actionsVersion.value++;
}

async function runAction(action: { run: (page: unknown) => unknown }) {
	// Awaited and caught. Neither, and a failing action leaves the draft mutated on
	// screen with no error at all -- CRM's `markWon` sets status to Won *before*
	// awaiting save(), so a user without write permission would watch the record flip
	// to Won and nothing else happen. Reloading discards the rejected draft.
	actionError.value = "";
	try {
		await action.run(controller.value?.page);
	} catch (e) {
		actionError.value = String((e as Error)?.message ?? e);
		await load();
	}
}

watch([doctype, docname], load, { immediate: true });
</script>
