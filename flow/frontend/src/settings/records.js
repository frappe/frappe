import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { dialog, toast } from "frappe-ui";
import { useDebouncedValue } from "@flow/ui-core/debounce.js";

import { call } from "../api/frappe.js";
import { newDoc } from "./specs.js";

// What a list of records and a record's form do, for settings and for the pages beside the
// chats, each in its own layout.

const PAGE_LENGTH = 200;

// A spec's records, searched by `query` (a ref) and a page at a time. A reload keeps the
// current rows on screen until its own arrive.
export function useRecordList(spec, { query, filters = () => ({}) }) {
	const debouncedQuery = useDebouncedValue(query, 300);
	const hasEnabled = spec.fields.some((field) => field.name === "enabled");
	const rows = ref([]);
	const loaded = ref(false);
	const loading = ref(false);
	const error = ref("");
	const hasMore = ref(false);
	let request = 0;

	// by value: a getter may hand back an equal object anew
	watch([debouncedQuery, () => JSON.stringify(filters())], () => load(), { immediate: true });
	onBeforeUnmount(() => request++);

	async function load(append = false) {
		if (append && loading.value) return;
		const own = ++request;
		loading.value = true;
		error.value = "";
		const query = debouncedQuery.value.trim().replace(/[\\%_]/g, "\\$&");
		try {
			const data = await call("frappe.client.get_list", {
				doctype: spec.doctype,
				fields: hasEnabled ? [...spec.listFields, "enabled"] : spec.listFields,
				filters: filters(),
				or_filters: query
					? (spec.searchFields ?? spec.listFields).map((field) => [
							field,
							"like",
							`%${query}%`,
					  ])
					: [],
				order_by: `${spec.orderBy ?? `${spec.titleField} asc`}, name asc`,
				limit_start: append ? rows.value.length : 0,
				limit_page_length: PAGE_LENGTH + 1,
			});
			if (own !== request) return;
			hasMore.value = data.length > PAGE_LENGTH;
			if (!append) rows.value = [];
			rows.value.push(...data.slice(0, PAGE_LENGTH));
			loaded.value = true;
		} catch (err) {
			if (own !== request) return;
			if (!append) rows.value = []; // so Retry starts over
			error.value = err.message;
		} finally {
			if (own === request) loading.value = false;
		}
	}

	// a deleted record goes now, not when the reload lands
	function drop(name) {
		rows.value = rows.value.filter((row) => row.name !== name);
		load();
	}

	return { rows, loaded, loading, error, hasMore, hasEnabled, load, drop, debouncedQuery };
}

// One document of `props.spec`'s doctype: loaded by `props.name` (or the single), or a blank new
// one. Multi-link fields are edited as name lists and written back as child rows. It reports
// to `emit` as "saved" and "deleted"; Cmd+S / Ctrl+S saves, as in the Desk, where `form` (the
// form element) sits: a page's record doesn't save under a dialog's.
export function useRecord(props, emit) {
	const page = inject("flowPage");
	const doc = ref(null);
	const original = ref("");
	const error = ref("");
	const saving = ref(false);
	const running = ref(null);
	const form = ref(null);

	const isNew = computed(() => !props.spec.single && !doc.value?.name);
	const canWrite = computed(() =>
		page.can(props.spec.doctype, isNew.value ? "create" : "write")
	);
	const canDelete = computed(
		() => !isNew.value && !props.spec.single && page.can(props.spec.doctype, "delete")
	);
	// a record not loaded, or that failed to load, has no edits
	const dirty = computed(() => !!doc.value && JSON.stringify(doc.value) !== original.value);
	const visibleFields = computed(() =>
		props.spec.fields.filter((field) => !field.when || field.when(doc.value))
	);
	const actions = computed(() =>
		(props.spec.actions ?? []).filter((action) => !action.when || action.when(doc.value))
	);
	const multilinks = computed(() =>
		props.spec.fields.filter((field) => field.type === "multilink")
	);
	const renameField = computed(() => props.spec.fields.find((field) => field.rename)?.name);

	function isLocked(field) {
		return !!field.locked?.(doc.value);
	}

	function adopt(data) {
		const value = { ...data };
		for (const field of multilinks.value)
			value[field.name] = (data[field.name] ?? []).map((row) => row[field.child]);
		doc.value = value;
		original.value = JSON.stringify(value);
	}

	async function load() {
		error.value = "";
		try {
			if (props.spec.single)
				adopt(await call("frappe.client.get", { doctype: props.spec.doctype }));
			else if (props.name)
				adopt(
					await call("frappe.client.get", {
						doctype: props.spec.doctype,
						name: props.name,
					})
				);
			else adopt(newDoc(props.spec));
		} catch (err) {
			error.value = err.message;
		}
	}
	onMounted(load);

	// pressed in the form's own dialog, or outside any for a form in none
	function onKey(event) {
		// in the launcher's panel, Cmd+S is the page's around it
		if (window.top !== window) return;
		if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
			event.preventDefault();
			const dialogOf = (el) => el?.closest?.("[role=dialog]") ?? null;
			if (canWrite.value && dialogOf(event.target) === dialogOf(form.value)) save();
		}
	}
	onMounted(() => window.addEventListener("keydown", onKey));
	onBeforeUnmount(() => window.removeEventListener("keydown", onKey));

	function payload(source = doc.value) {
		const value = { ...source, doctype: props.spec.doctype };
		for (const field of multilinks.value)
			value[field.name] = (source[field.name] ?? []).map((name) => ({
				[field.child]: name,
			}));
		// a JSON column rejects "": an empty editor means no value at all
		for (const field of props.spec.fields)
			if (field.language === "json" && !value[field.name]) value[field.name] = null;
		return value;
	}

	async function save() {
		if (saving.value || !dirty.value) return;
		saving.value = true;
		error.value = "";
		try {
			const from = doc.value.name;
			const to = renameTo();
			const method = isNew.value ? "frappe.client.insert" : "frappe.client.save";
			const saved = to ? await rename(to) : await call(method, { doc: payload() });
			adopt(saved);
			if (to) page.renamed(props.spec.doctype, from, to);
			page.changed(props.spec.doctype);
			toast.success(
				to ? "Renamed" : method === "frappe.client.insert" ? "Created" : "Saved"
			);
			emit("saved", saved);
		} catch (err) {
			error.value = err.message;
		} finally {
			saving.value = false;
		}
	}

	// a saved record is named after its rename field, so changing that field renames it
	function renameTo() {
		const field = renameField.value;
		if (isNew.value || !field) return null;
		const to = (doc.value[field] ?? "").trim();
		return to && to !== doc.value.name && to !== JSON.parse(original.value)[field] ? to : null;
	}

	// the other edits save under the current name first; Frappe's rename then moves every
	// link to the record and sets the field to the new name
	async function rename(to) {
		const field = renameField.value;
		const rest = { ...doc.value, [field]: JSON.parse(original.value)[field] };
		if (JSON.stringify(rest) !== original.value) {
			const saved = await call("frappe.client.save", { doc: payload(rest) });
			adopt(saved);
			// these edits stand even if the rename fails
			page.changed(props.spec.doctype);
			emit("saved", saved);
			doc.value[field] = to;
		}
		await call("frappe.client.rename_doc", {
			doctype: props.spec.doctype,
			old_name: doc.value.name,
			new_name: to,
		});
		return call("frappe.client.get", { doctype: props.spec.doctype, name: to });
	}

	function remove() {
		dialog.danger({
			title: `Delete this ${props.spec.singular}?`,
			size: "lg",
			message: `“${
				doc.value[props.spec.titleField] || doc.value.name
			}” will be permanently removed.`,
			onConfirm: async ({ close }) => {
				try {
					await call("frappe.client.delete", {
						doctype: props.spec.doctype,
						name: doc.value.name,
					});
					page.changed(props.spec.doctype);
					toast.success("Deleted");
					close();
					emit("deleted");
				} catch (err) {
					error.value = err.message;
					close();
				}
			},
		});
	}

	// a doc method's answer; frappe returns the whole body when it also sends docs
	async function runAction(action) {
		running.value = action.label;
		error.value = "";
		try {
			const result = await call("run_doc_method", {
				dt: props.spec.doctype,
				dn: doc.value.name,
				method: action.method,
				args: action.args ?? {},
			});
			const message = result?.docs ? result.message : result;
			toast.success(message?.message ?? action.success ?? "Done");
			await load();
		} catch (err) {
			error.value = err.message;
		} finally {
			running.value = null;
		}
	}

	return {
		doc,
		form,
		error,
		saving,
		running,
		isNew,
		canWrite,
		canDelete,
		dirty,
		visibleFields,
		actions,
		isLocked,
		save,
		remove,
		runAction,
	};
}
