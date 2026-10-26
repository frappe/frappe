<!--
  A new record before its first save: the record-page engine with the header row and the New
  Record form only. The first save inserts it and replaces the address with the saved record's.
-->
<template>
	<PageFrame :scroll="false" :state="state">
		<template v-if="painted" #aboveHeader>
			<FrameBands :bands="frame.before" :page="painted.page" />
		</template>

		<template v-if="frame.header && (!painted || !isEmptyHeader(header))" #header>
			<RecordHeader
				v-if="painted"
				:projection="header"
				:page="painted.page"
				:dirty="true"
				:saving="painted.isSaving.value"
				:favourites="[]"
				:favourited="false"
				@run="runHeaderItem"
			/>
			<h1 v-else-if="state" class="text-lg font-semibold">{{ title }}</h1>
			<HeaderSkeleton v-else />
		</template>

		<FrameBands v-if="painted" :bands="frame.between" :page="painted.page" />

		<template v-if="frame.body">
			<BodyColumns
				v-if="painted"
				:items="bodyItems"
				:page="painted.page"
				:user="boot.session.user.name"
			>
				<template #form>
					<!-- Locked while a save runs, so the reply never lands over an edit. -->
					<div ref="formRoot" data-record-form :inert="painted.isSaving.value">
						<FormLayout
							v-if="form.length"
							v-model:doc="doc"
							v-model:sections="formSections"
							:layout="form"
							:tab="formTab"
							:class="FORM_CLASSES"
							@update:tab="formTab = $event"
							@update:activeTab="activeFormTab = $event"
						/>
					</div>
				</template>
			</BodyColumns>

			<div v-else class="mx-auto w-full max-w-3xl px-[--page-gutter] py-6">
				<FormSkeleton :columns="2" :fields="6" />
			</div>
		</template>

		<FrameBands v-if="painted" :bands="frame.after" :page="painted.page" />

		<PageDialogs v-if="controller" :controller="controller" />
	</PageFrame>
</template>

<script setup lang="ts">
import { computed, inject, onUnmounted, ref, shallowRef } from "vue";
import {
	onBeforeRouteLeave,
	onBeforeRouteUpdate,
	useRouter,
	type LocationQuery,
} from "vue-router";
import { toast } from "frappe-ui";
import { createDocument, isApiError } from "@framework/ui/api";
import { FormLayout } from "@framework/ui/FormLayout";
import {
	createRecordPage,
	errorMessage,
	formItems,
	isEmptyHeader,
	joinForm,
	loadRecordScripts,
	projectFrame,
	useFormLayout,
	type HeaderItem,
	type RecordPageApi,
	type RecordPageController,
} from "@/recordPage";
import { useCreateRight } from "@/createRight";
import { __ } from "@/i18n";
import { routeFor } from "@/router/routeFor";
import { openCreate } from "@/shell/create";
import { OpenSettingsKey } from "@/shell/openSettings";
import PageFrame from "@/shell/PageFrame.vue";
import { failedState, type PageStateValue } from "@/shell/pageState";
import type { Boot } from "@/boot";
import {
	fetchNewDocument,
	fieldDefaults,
	insertBody,
	queryValues,
	withNameField,
} from "@/newRecordValues";
import BodyColumns from "./body/BodyColumns.vue";
import PageDialogs from "./dialogs/PageDialogs.vue";
import FrameBands from "./FrameBands.vue";
import NotSavedBadge from "./NotSavedBadge.vue";
import RecordHeader from "./RecordHeader.vue";
import FormSkeleton from "./skeletons/FormSkeleton.vue";
import HeaderSkeleton from "./skeletons/HeaderSkeleton.vue";
import { discardChanges } from "./discardChanges";
import { FORM_CLASSES } from "./formClasses";
import { landOnField, stopLanding } from "./landOnField";
import { openingKey } from "./openingKey";
import { Visit } from "./visit";
import { fetchMeta } from "./metaSource";
import { provideRecordCommits } from "./recordCommits";
import { saveRecord } from "./recordSource";
import { projectRecordHeader } from "./recordHeaderProjection";
import { runSave, useUnloadGuard } from "./recordSave";
import { shownInDialog, stripTags } from "./saveResponse";

const props = defineProps<{ doctype: string; query: LocationQuery }>();

// No record read has run, so there are no record rights yet; the insert checks them.
const NO_RIGHTS = {};

const boot = inject<Boot>("boot")!;
const openSettings = inject(OpenSettingsKey, undefined);
const router = useRouter();
const canCreate = useCreateRight(props.doctype);

const doc = ref<Record<string, any>>({});
const saved = ref<Record<string, any>>({});
const meta = ref<any>(null);
// The draft after `onOpen`, then the inserted record: leaving asks only about changes since.
const opened = ref<string | null>(null);
// The values the layout row is picked against, set once, so typing never switches the row.
const openingValues = ref<Record<string, any>>({});
const state = shallowRef<PageStateValue | null>(null);
const controller = shallowRef<RecordPageController | null>(null);
const painted = computed(() => (controller.value?.ready.value ? controller.value : null));
const actionsVersion = ref(0);
const formTab = ref("");
const activeFormTab = ref("");
const formSections = ref<Record<string, boolean>>({});
const formRoot = ref<HTMLElement | null>(null);
let insertedName: string | null = null;
let visit = new Visit();

const title = computed(() => __("New {0}", [__(props.doctype)]));
const dirty = computed(() => opened.value !== null && JSON.stringify(doc.value) !== opened.value);

const layout = useFormLayout({
	doctype: props.doctype,
	type: "New Record",
	doc: openingValues,
	fallback: "meta",
	overrides: () => controller.value?.fields.resolve() ?? {},
	tabOverrides: () => controller.value?.form.tabs.resolve() ?? {},
});
// Types what "Edit full form" carried from the dialog's inline fields, shown here or not.
const quickEntry = Object.keys(props.query).length
	? useFormLayout({
			doctype: props.doctype,
			type: "Quick Entry",
			doc: openingValues,
			fallback: "none",
	  })
	: null;

const header = computed(() => {
	actionsVersion.value;
	return projectRecordHeader(controller.value?.header.resolve() ?? []);
});

const frame = computed(() => {
	actionsVersion.value;
	return projectFrame(controller.value?.frame.resolve() ?? []);
});

const bodyItems = computed(() => {
	actionsVersion.value;
	return (controller.value?.body.visible() ?? []).filter((item) => item.name !== "panel");
});

const detailsForm = computed(() => withNameField(layout.layout.value, meta.value));
const form = computed(() => {
	actionsVersion.value;
	const page = controller.value;
	return page ? joinForm(detailsForm.value, page.form.resolve(), page.page) : detailsForm.value;
});

provideRecordCommits(() => controller.value);

const landing = {
	root: () => formRoot.value,
	layout: () => form.value,
	showTab: (identity: string) => void (formTab.value = identity),
};

void open();

/** Meta, defaults, layout and scripts at once, then the first paint; stops when the visit ends. */
async function open() {
	visit = visit.next();
	const opening = visit;
	controller.value?.leave();
	controller.value = null;
	opened.value = null;
	state.value = null;
	void loadRecordScripts(props.doctype);
	const newDocument = fetchNewDocument(props.doctype);
	// Read after the meta and the create right; a page that stops before then drops the failure.
	newDocument.catch(() => {});
	try {
		meta.value = await fetchMeta(props.doctype);
		if (!opening.current()) return;
		if (!canCreate.value) {
			state.value = { name: "noPermission" };
			return;
		}
		const newDoc = await newDocument;
		if (!opening.current()) return;
		const values = {
			...fieldDefaults(newDoc, meta.value),
			...queryValues(props.query, meta.value),
		};
		openingValues.value = values;
		doc.value = JSON.parse(JSON.stringify(values));
	} catch (exception) {
		if (opening.current()) state.value = failedState(exception, open);
		return;
	}

	const created = buildController();
	await Promise.all([layout.settled(), quickEntry?.settled()]);
	if (!opening.current()) return;
	const carried = [...(quickEntry?.layout.value ?? []), ...detailsForm.value];
	doc.value = { ...doc.value, ...queryValues(props.query, meta.value, carried) };
	await created.refresh();
	if (!opening.current()) return;
	opened.value = JSON.stringify(doc.value);
	actionsVersion.value++;
}

function buildController() {
	const created = createRecordPage({
		doctype: props.doctype,
		docname: "",
		doc,
		saved,
		meta,
		perms: () => NO_RIGHTS,
		isDirty: () => dirty.value,
		isNew: () => insertedName === null,
		activeTab: () => "details",
		activateTab: () => {},
		formLayout: () => detailsForm.value,
		activeFormTab: () => activeFormTab.value,
		activateFormTab: (identity) => void (formTab.value = identity),
		focusField: (fieldname, cursor) => void landOnField(landing, fieldname, cursor),
		save: write,
		onSaved: openSaved,
		reload: open,
		router,
		openCreate,
		openSettings,
		sourcesReady: () => loadRecordScripts(props.doctype),
		actFailed,
		activityRows: () => [],
		scrollToActivity: async () => false,
		reloadActivity: async () => {},
		fileRows: () => [],
		reloadFiles: async () => {},
	});
	created.header.provideBuiltins(headerBuiltins);
	created.form.provideBuiltins(() => formItems(detailsForm.value));
	controller.value = created;
	return created;
}

function headerBuiltins(): HeaderItem[] {
	return [
		{
			name: "doctype",
			label: props.doctype,
			zone: "left",
			display: "crumb",
			href: router.resolve(routeFor(props.doctype)).path,
		},
		{ name: "record", label: title.value, zone: "left", display: "crumb" },
		{ name: "notSaved", label: __("Not Saved"), zone: "left", component: NotSavedBadge },
		{ name: "save", label: __("Save"), display: "button", key: "Mod+S", run: save },
	];
}

/** Inserts the record, sending a prompt name as `__newname`, then saves the inserted one in place. */
async function write() {
	const sent = JSON.parse(JSON.stringify(doc.value));
	try {
		const document = insertedName
			? await saveRecord(props.doctype, sent)
			: (await createDocument(props.doctype, insertBody({}, sent))).data;
		insertedName = document.name;
		saved.value = { ...document };
		opened.value = JSON.stringify(document);
		doc.value = JSON.parse(JSON.stringify(document));
	} catch (exception) {
		if (!isApiError(exception)) throw exception;
		controller.value?.fieldErrors.markRefused(exception.fieldErrors, doc.value);
		throw new Error(stripTags(exception.message));
	}
}

async function openSaved() {
	if (insertedName) await router.replace(routeFor(props.doctype, insertedName));
}

function runHeaderItem(item: HeaderItem) {
	if (item.run) void controller.value?.perform(`header.${item.name}`);
}

// No reload: the record has no saved copy to go back to, so the draft stays.
function actFailed(exception: unknown) {
	if (!shownInDialog(exception)) toast.error(errorMessage(exception));
}

/** After the insert, Save with no changes only opens the saved record again. */
function save(page: RecordPageApi) {
	return insertedName && !dirty.value ? openSaved() : runSave(page);
}

async function confirmLeave() {
	if (!dirty.value || !controller.value) return true;
	return discardChanges(controller.value.page.dialog.confirm);
}

onBeforeRouteLeave(confirmLeave);
onBeforeRouteUpdate((to, from) => openingKey(to) === openingKey(from) || confirmLeave());

useUnloadGuard(() => dirty.value);

onUnmounted(() => {
	stopLanding();
	visit.end();
	controller.value?.leave();
});
</script>
