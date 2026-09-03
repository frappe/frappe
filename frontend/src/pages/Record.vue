<!--
  The generated record page every app gets at /apps/<prefix>/<slug>/<name>: a minimal host for
  the record-page engine, with no form layout, tabs or panel.
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
import { createRecordPage, type RecordPageController } from "@/recordPage";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";

const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;
const route = useRoute();
const router = useRouter();

const doc = ref<Record<string, any>>({});
const saved = ref<Record<string, any>>({});
const meta = ref<any>(null);
const error = ref("");
// Apart from `error`: a failed action must not blank the record (the field list is in its v-else).
const actionError = ref("");
const controller = shallowRef<RecordPageController | null>(null);
const actionsVersion = ref(0);

// The slower of two in-flight loads must not win: `save()` would then POST the wrong record.
let generation = 0;

const doctype = computed(() => addresses.doctypeOf(String(route.params.doctype)));
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

	// Blanked before the fetch: the heading changes synchronously, and the old controller's quick
	// actions close over the previous page. `saved` goes with `doc` so `isDirty` stays false.
	doc.value = {};
	saved.value = {};
	controller.value = null;
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
		// No tab strip on this page, so activation is a no-op.
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
	// Refuse to write the wrong record if the route moved while an action ran.
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
	// Awaited and caught: a failing action would otherwise leave the draft mutated on screen
	// with no error. Reloading discards the rejected draft.
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
