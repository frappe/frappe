<!--
  The generated record page every app gets at /apps/<prefix>/<slug>/<name>: a host for the
  record-page engine with a real header row and panel, no form layout yet, and its own scroll.
-->
<template>
	<PageFrame :scroll="false">
		<template v-if="doctype" #header>
			<RecordHeader
				v-if="controller"
				:projection="header"
				:dirty="dirty"
				:saving="saving"
				@run="runAction"
			/>
			<div v-else class="flex items-center gap-3">
				<h1 class="text-lg font-semibold">{{ route.params.name }}</h1>
				<span class="text-sm text-ink-gray-5">{{ doctype }}</span>
			</div>
		</template>

		<p v-if="!doctype" class="py-5 text-sm text-ink-gray-6" :class="pageGutter">
			No doctype is served at <code>{{ route.params.doctype }}</code> under this prefix.
		</p>

		<div v-else class="flex min-h-0 flex-1">
			<ScrollArea class="min-h-0 flex-1" :viewportClass="[pageGutter, 'py-5']">
				<p v-if="actionError" class="text-sm text-ink-red-4">{{ actionError }}</p>
				<p v-if="error" class="text-sm text-ink-red-4">{{ error }}</p>

				<dl v-else class="grid max-w-2xl grid-cols-[12rem_1fr] gap-y-1.5 text-sm">
					<template v-for="[field, value] in fields" :key="field">
						<dt class="text-ink-gray-6" :data-fieldname="field">{{ field }}</dt>
						<dd class="text-ink-gray-8">{{ value }}</dd>
					</template>
				</dl>
			</ScrollArea>

			<RecordPanel
				v-if="controller && !error"
				v-model:doc="doc"
				:user="boot.user.name"
				:doctype="doctype"
				:docname="docname"
				:controller="controller"
				:meta="meta"
				:docinfo="docinfo"
				:sections="sections"
				:disclosure="disclosure"
				:run="runAction"
				@expand="expand"
			/>
		</div>
	</PageFrame>
</template>

<script setup lang="ts">
import { computed, inject, ref, shallowRef, watch, type ComputedRef } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ScrollArea } from "frappe-ui";
import type { FieldNode, FormLayoutSchema } from "@framework/ui/components/FormLayout/types";
import {
	createRecordPage,
	loadClientScripts,
	projectHeader,
	useFormLayout,
	type HeaderItem,
	type QuickAction,
	type RecordPageController,
} from "@/recordPage";
import { routeFor } from "@/router/routeFor";
import RecordHeader from "./record/RecordHeader.vue";
import { fetchMeta } from "./record/metaSource";
import { PANEL_BUILTINS } from "./record/panel/builtins";
import { quickActionBuiltins } from "./record/quickActionBuiltins";
import type { DocInfo } from "./record/panel/context";
import { useDisclosure } from "./record/panel/disclosure";
import { layoutItems, layoutSections } from "./record/panel/panelEntries";
import RecordPanel from "./record/panel/RecordPanel.vue";
import PageFrame, { pageGutter } from "@/shell/PageFrame.vue";
import type { Boot } from "@/boot";
import type { Addresses } from "@/addresses";

const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;
const route = useRoute();
const router = useRouter();

const doc = ref<Record<string, any>>({});
const saved = ref<Record<string, any>>({});
const meta = ref<any>(null);
const docinfo = ref<DocInfo | null>(null);
const error = ref("");
// Apart from `error`: a failed action must not blank the record (the field list is in its v-else).
const actionError = ref("");
const controller = shallowRef<RecordPageController | null>(null);
// The doctype's Side Panel layout, or nothing: the panel never falls back to the Details layout.
const panelLayout = shallowRef<ComputedRef<FormLayoutSchema> | null>(null);
const actionsVersion = ref(0);
const saving = ref(false);

// The right zone keeps this many top-level controls; the rest demote into `⋯`.
const HEADER_BUDGET = 3;

// The slower of two in-flight loads must not win: `save()` would then POST the wrong record.
let generation = 0;

const doctype = computed(() => addresses.doctypeOf(String(route.params.doctype)));
const docname = computed(() => String(route.params.name));

const fields = computed(() =>
	Object.entries(doc.value ?? {})
		.filter(([key]) => !key.startsWith("_") && key !== "doctype")
		.slice(0, 25)
);

const dirty = computed(() => JSON.stringify(doc.value) !== JSON.stringify(saved.value));

const header = computed(() => {
	actionsVersion.value;
	const resolved = controller.value?.header.resolve() ?? [];
	return projectHeader(resolved, HEADER_BUDGET);
});

// Resolved against the draft, as the form's own `depends_on` is.
const sections = computed(() => layoutSections(panelLayout.value?.value ?? [], doc.value));

// Open sections are the reader's, per doctype; the surface's labelled items are what there is to open.
const disclosure = useDisclosure(
	() => boot.user.name,
	() => `Record:${doctype.value}`,
	() =>
		(controller.value?.panelSections.visible() ?? [])
			.filter((item) => item.label)
			.map((item) => ({ name: item.name, opened: item.opened !== false }))
);

// The row's built-ins, re-read on every resolve so the title crumb tracks the draft.
function headerBuiltins(): HeaderItem[] {
	const title = doc.value[meta.value?.title_field] || docname.value;
	return [
		{
			name: "doctype",
			label: doctype.value ?? "",
			zone: "left",
			display: "crumb",
			href: router.resolve(routeFor(doctype.value!)).path,
		},
		{ name: "record", label: String(title), zone: "left", display: "crumb" },
		{ name: "save", label: "Save", display: "button", run: saveFromHeader },
	];
}

// Three built-ins first, then the Side Panel layout's sections, as they resolve now.
function panelBuiltins() {
	return [...PANEL_BUILTINS, ...layoutItems(sections.value)];
}

// Not through `runAction`: a failed save must keep the draft on screen, not reload over it.
async function saveFromHeader() {
	if (!dirty.value) return;
	actionError.value = "";
	try {
		await save();
	} catch (e) {
		actionError.value = String((e as Error)?.message ?? e);
	}
}

/** `getdoc`: the document and its sidecar in one round trip; an absent record answers no docs. */
async function fetchDoc(target: { doctype: string; name: string }) {
	const res = await fetch(
		`/api/method/frappe.desk.form.load.getdoc?${new URLSearchParams(target)}`
	);
	if (!res.ok) throw new Error(String(res.status));
	const body = await res.json();
	const document = body.docs?.[0];
	if (!document) throw new Error("404");
	return { document, docinfo: body.docinfo as DocInfo };
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
	docinfo.value = null;
	controller.value = null;
	panelLayout.value = null;
	disclosure.reset();
	try {
		const [loaded, metadata] = await Promise.all([
			fetchDoc(target),
			fetchMeta(target.doctype),
		]);
		if (mine !== generation) return;
		saved.value = { ...loaded.document };
		doc.value = JSON.parse(JSON.stringify(loaded.document));
		docinfo.value = loaded.docinfo;
		meta.value = metadata;
	} catch (e) {
		if (mine !== generation) return;
		error.value =
			String(e) === "Error: 403"
				? "You do not have permission to read this record."
				: "Not found.";
		return;
	}

	const created = createRecordPage({
		doctype: target.doctype,
		docname: target.name,
		doc,
		saved,
		meta,
		perms: () => docinfo.value?.permissions ?? {},
		isDirty: () => dirty.value,
		// No tab strip on this page, so activation is a no-op.
		activeTab: () => "",
		activateTab: () => {},
		discloseSection: disclosure.disclose,
		save,
		reload: load,
		router,
		sourcesReady: () => loadClientScripts(target.doctype),
	});
	created.header.provideBuiltins(headerBuiltins);
	created.quickActions.provideBuiltins(() =>
		quickActionBuiltins(docinfo.value?.permissions ?? {})
	);
	created.panelSections.provideBuiltins(panelBuiltins);
	// Against the saved document, so a keystroke cannot switch the layout under the reader.
	const layoutSource = useFormLayout({
		doctype: target.doctype,
		type: "Side Panel",
		doc: saved,
		fallback: "none",
		overrides: () => created.fields.resolve(),
	});
	panelLayout.value = layoutSource.layout;
	controller.value = created;

	// The first replay must see the layout's sections, or a script's act on one is dropped as unknown.
	await layoutSource.settled();
	if (mine !== generation) return;
	await created.refresh();
	if (mine !== generation) return;
	// A reload triggered by a failed action must not wipe the message explaining it.
	actionError.value = carriedActionError;
	actionsVersion.value++;
}

// One request at a time: a `page.save()` that lands mid-flight awaits the one in flight.
let inFlight: Promise<void> | null = null;

async function save() {
	// Refuse to write the wrong record if the route moved while an action ran.
	if (doc.value.name !== docname.value || doctype.value === null) {
		throw new Error("The record changed while saving; nothing was written.");
	}
	if (!inFlight) inFlight = write().finally(() => (inFlight = null));
	await inFlight;
}

async function write() {
	const mine = generation;
	saving.value = true;
	try {
		const res = await fetch("/api/method/frappe.client.save", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": boot.csrf_token,
			},
			body: JSON.stringify({ doc: { ...doc.value, doctype: doctype.value } }),
		});
		if (!res.ok) throw new Error(`Save failed with ${res.status}`);

		const document = (await res.json()).message;
		if (mine !== generation) return;
		saved.value = { ...document };
		doc.value = JSON.parse(JSON.stringify(document));
	} finally {
		saving.value = false;
	}
	await controller.value?.refresh();
	actionsVersion.value++;
}

async function runAction(action: QuickAction | HeaderItem) {
	// Awaited and caught: a failing action would otherwise leave the draft mutated on screen
	// with no error. Reloading discards the rejected draft.
	actionError.value = "";
	try {
		await action.run?.(controller.value!.page);
	} catch (e) {
		actionError.value = String((e as Error)?.message ?? e);
		await load();
	}
}

// A panel row with no honest control opens where the main column shows the field.
function expand(field: FieldNode) {
	document
		.querySelector(`dl [data-fieldname="${field.fieldname}"]`)
		?.scrollIntoView({ block: "center" });
}

watch([doctype, docname], load, { immediate: true });
</script>
