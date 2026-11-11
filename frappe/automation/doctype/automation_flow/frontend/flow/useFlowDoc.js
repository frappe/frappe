import { computed, reactive, ref, shallowRef, watch } from "vue";
import { toast } from "frappe-ui";
import { __ } from "frappe/i18n";
import {
	copyDocument,
	createDocument,
	getDocument,
	isApiError,
	updateDocument,
} from "@framework/ui/api";
import { htmlToText } from "@framework/ui/RichText";
import { FlowHistory } from "./FlowHistory";
import { saveErrors, withoutEdited } from "./flowErrors";
import {
	FLOW_DOCTYPE,
	copySource,
	fromServer,
	keepStepIds,
	openingFlow,
	savedKey,
	toPayload,
	withServerFields,
} from "./flowDoc";

/** The flow a builder page edits; `name` is null before its first save, and `query` is the address's. */
export function useFlowDoc(name, query = {}) {
	const doc = ref(null);
	const loading = ref(true);
	const failure = shallowRef(null);
	const saving = ref(false);
	const conflict = ref(false);
	const errors = ref({});
	const history = new FlowHistory();
	const canUndo = ref(false);
	const canRedo = ref(false);
	let current = name;
	let saved = "";
	let restoring = null;
	let reads = 0;

	const isNew = computed(() => !doc.value?.name);
	const unsaved = computed(() => Boolean(doc.value) && savedKey(doc.value) !== saved);

	watch(() => doc.value && JSON.stringify(doc.value), onEdit);

	function onEdit(now, before) {
		if (now === restoring) {
			restoring = null;
			return;
		}
		if (before == null || now == null) return;
		history.record(before);
		syncHistory();
		if (Object.keys(errors.value).length)
			errors.value = withoutEdited(errors.value, JSON.parse(before), doc.value);
	}

	function syncHistory() {
		canUndo.value = history.canUndo;
		canRedo.value = history.canRedo;
	}

	function adopt(next) {
		restoring = JSON.stringify(next);
		doc.value = next;
		saved = savedKey(next);
	}

	async function load(target = current) {
		const read = ++reads;
		current = target;
		loading.value = true;
		failure.value = null;
		try {
			const next = target
				? fromServer((await getDocument(FLOW_DOCTYPE, target)).data)
				: await opening();
			if (read !== reads) return;
			adopt(next);
			conflict.value = false;
			errors.value = {};
			history.clear();
			syncHistory();
		} catch (error) {
			if (read !== reads) return;
			if (doc.value) toast.error(__("The flow could not be reloaded"));
			else failure.value = error;
		} finally {
			if (read === reads) loading.value = false;
		}
	}

	async function opening() {
		const source = copySource(query);
		const copy = source ? (await copyDocument(FLOW_DOCTYPE, source)).data : null;
		return openingFlow(copy, query);
	}

	/** True when the flow is saved; a refusal is shown on the page and returns false. */
	async function save() {
		if (saving.value || !doc.value) return false;
		if (!doc.value.title?.trim()) {
			toast.error(__("Give the flow a title"));
			return false;
		}
		saving.value = true;
		errors.value = {};
		try {
			const payload = toPayload(doc.value);
			const { data } = isNew.value
				? await createDocument(FLOW_DOCTYPE, payload)
				: await updateDocument(FLOW_DOCTYPE, doc.value.name, payload);
			const next = fromServer(data);
			keepStepIds(doc.value.actions, next.actions);
			adopt(next);
			current = next.name;
			return true;
		} catch (error) {
			refuse(error);
			return false;
		} finally {
			saving.value = false;
		}
	}

	function refuse(error) {
		if (isApiError(error) && error.isTimestampMismatch) {
			conflict.value = true;
			return;
		}
		const refused = saveErrors(error, doc.value.actions);
		errors.value = refused.errors;
		const message = htmlToText(refused.general) || firstMessage(refused.errors);
		toast.error(message || __("The flow could not be saved"));
	}

	function restore(snapshot) {
		if (snapshot === null) return;
		const next = withServerFields(JSON.parse(snapshot), doc.value);
		restoring = JSON.stringify(next);
		doc.value = next;
		errors.value = {};
		syncHistory();
	}

	function undo() {
		restore(history.undo(JSON.stringify(doc.value)));
	}

	function redo() {
		restore(history.redo(JSON.stringify(doc.value)));
	}

	return reactive({
		doc,
		loading,
		failure,
		saving,
		conflict,
		errors,
		isNew,
		unsaved,
		canUndo,
		canRedo,
		current: () => current,
		load,
		save,
		undo,
		redo,
	});
}

function firstMessage(errors) {
	return Object.values(errors)[0]?.[0] || "";
}
