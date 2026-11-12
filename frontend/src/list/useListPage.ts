// One view of a doctype: the state the list page's controls edit, seeded from the app default under
// the site's and the person's stored rows, mirrored to the URL query, and written back on the person's acts.
import { useDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { useDocPermissions } from "@framework/ui/useDocPermissions";
import type { FilterCondition, FilterField } from "@framework/ui/Filter";
import type { Sort } from "@framework/ui/SortBy";
import { holdFresh } from "@framework/ui/utils";
import {
	computed,
	getCurrentScope,
	onScopeDispose,
	ref,
	watch,
	type ComputedRef,
	type Ref,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import { defaultSort, sameSort, type ListMeta } from "./defaults";
import {
	addressFromQuery,
	createValues,
	ownedKeys,
	queryFromAddress,
	sameFilters,
	sameQuery,
} from "./query";
import type { SavedView } from "./savedView";
import {
	filtersFrom,
	quickFilterFieldsFrom,
	sortFrom,
	toStoredQuickFilterFields,
	type ListSettings,
	type ListSettingsKey,
} from "./storedSettings";
import { useListSettings } from "./useListSettings";
import type { View } from "./view";

export interface ListPage {
	/** What the page hands its renderer, or a replacement page. */
	view: View;
	/** Written to the person's row when customizing ends. */
	quickFilterFields: Ref<FilterField[] | undefined>;
	customizing: Ref<boolean>;
	/** Why the doctype's meta could not be read. */
	metaError: ComputedRef<unknown>;
	reloadMeta: () => void;
	/** The site's defaults, which everyone without their own inherits; a System Manager's act. */
	saveForSite: (settings: ListSettings) => Promise<void>;
	resetForSite: (key: ListSettingsKey) => Promise<void>;
	/** What a new record from this list starts with. */
	createValues: ComputedRef<Record<string, unknown>>;
}

/** The view a list address opens when it names none: the plain List view. */
export const PLAIN_LIST: SavedView = {
	key: "list",
	label: "",
	type: "List",
	layer: null,
	applies: true,
};

export function useListPage(doctype: string, opened: SavedView = PLAIN_LIST): ListPage {
	const route = useRoute();
	const router = useRouter();
	const { meta, error, refreshing, refreshed, reload: reloadMeta } = useDoctypeMeta(doctype);
	const permissions = useDocPermissions(doctype);
	const settings = useListSettings(doctype);
	const listMeta = computed(() => meta.value as ListMeta | null);
	const fields = computed(() => listMeta.value?.fields ?? []);

	const filters = ref<FilterCondition[]>([]);
	const sort = ref<Sort[]>([]);
	const quickFilterFields = ref<FilterField[] | undefined>();
	const customizing = ref(false);
	// The renderer's keys the person changed; the stored rows show through every other key.
	const changed = ref<Record<string, unknown>>({});
	const seeded = ref(false);
	// What the page last set itself, per key: a change that matches it is not the person's act.
	const applied: Partial<Record<ListSettingsKey, string>> = {};
	const acted = new Set<ListSettingsKey>();

	const ready = computed(
		() => Boolean(listMeta.value) && settings.loaded.value && !permissions.loading.value
	);

	const readable = (fieldname: string) => {
		const field = fields.value.find((one) => one.fieldname === fieldname);
		return !field || permissions.fieldAccess(field) !== "none";
	};

	function resolvedSort(): Sort[] {
		const stored = sortFrom(settings.stored.value.sort, fields.value, readable, listMeta.value ?? {});
		return stored.length ? stored : defaultSort(listMeta.value!);
	}

	function resolvedFilters(): FilterCondition[] {
		return filtersFrom(settings.stored.value.filters, doctype, fields.value, readable);
	}

	function resolvedQuickFilterFields(): FilterField[] | undefined {
		const stored = settings.stored.value.quick_filter_fields;
		if (!stored) return undefined;
		return quickFilterFieldsFrom(stored, doctype, fields.value, readable);
	}

	function applyStored() {
		changed.value = {};
		applyQuickFilterFields();
	}

	function applyQuickFilterFields() {
		quickFilterFields.value = resolvedQuickFilterFields();
		applied.quick_filter_fields = JSON.stringify(
			quickFilterFields.value && toStoredQuickFilterFields(quickFilterFields.value)
		);
	}

	function readQuery(value: ListMeta) {
		const address = addressFromQuery(route.query, doctype, value.fields ?? []);
		filters.value = address.filters ?? resolvedFilters();
		readSort();
	}

	/** After a row changed under the page: the sort follows, a filter still being typed stays. */
	function readSort() {
		const address = addressFromQuery(route.query, doctype, fields.value);
		sort.value = address.sort ?? resolvedSort();
		applied.sort = JSON.stringify(sort.value);
	}

	watch(
		ready,
		(value) => {
			if (!value || seeded.value) return;
			applyStored();
			readQuery(listMeta.value!);
			seeded.value = true;
		},
		{ immediate: true }
	);

	// After a DocType change the page shows the stale meta and settings, then both fresh ones in one step.
	if (refreshing.value || settings.refreshing.value) {
		const release = holdFresh();
		if (getCurrentScope()) onScopeDispose(release);
		void Promise.all([refreshed(), settings.refreshed()]).then(() => {
			release();
			applyFresh();
		});
	}

	/** Each setting the page set from stale settings follows the fresh ones, unless the person changed it. */
	function applyFresh() {
		if (!seeded.value) return;
		if (!acted.has("quick_filter_fields")) applyQuickFilterFields();
		if (!acted.has("sort")) readSort();
	}

	// Only a query the page did not write itself is read back: Back, Forward, a pasted link.
	watch(
		() => route.query,
		(query) => {
			if (seeded.value && !sameQuery(query, stateQuery())) readQuery(listMeta.value!);
		}
	);

	// A replace, so the tweak is not a step Back has to undo. A landed write moves the resolved
	// sort, so the URL is spelled again and a `_sort` that became the default goes.
	watch([filters, sort, settings.stored], writeQuery, { deep: true });

	function writeQuery() {
		if (!seeded.value || sameQuery(route.query, stateQuery())) return;
		router.replace({ query: stateQuery(), hash: route.hash }).catch(() => {});
	}

	/** The query the state spells: foreign keys kept, the resolved sort left unwritten. */
	function stateQuery() {
		const owned = ownedKeys(doctype, fields.value);
		const kept = Object.fromEntries(
			Object.entries(route.query).filter(([key]) => !owned.has(key))
		);
		const written = sameSort(sort.value, resolvedSort()) ? [] : sort.value;
		const spelled = sameFilters(filters.value, resolvedFilters()) ? [] : filters.value;
		return { ...kept, ...queryFromAddress({ filters: spelled, sort: written }) };
	}

	// The person's own acts write; a value the page set itself, from a row or the URL, does not.
	watch(sort, (value) => persist("sort", value), { deep: true });
	watch(customizing, (now, before) => {
		if (before && !now && quickFilterFields.value) {
			persist("quick_filter_fields", toStoredQuickFilterFields(quickFilterFields.value));
		}
	});

	function persist<Key extends ListSettingsKey>(key: Key, value: ListSettings[Key]) {
		const json = JSON.stringify(value);
		if (!seeded.value || applied[key] === json) return;
		applied[key] = json;
		acted.add(key);
		settings.save({ [key]: value });
	}

	const viewSettings = computed(() => ({ ...settings.stored.value, ...changed.value }));

	/** A renderer's change to its own keys: kept in page state and written to the person's row. */
	function update(patch: Record<string, unknown>) {
		const current = viewSettings.value as Record<string, unknown>;
		const moved = Object.entries(patch).filter(
			([key, value]) => JSON.stringify(value) !== JSON.stringify(current[key])
		);
		if (!moved.length) return;
		changed.value = { ...changed.value, ...Object.fromEntries(moved) };
		for (const [key, value] of moved) persist(key as ListSettingsKey, value as never);
	}

	const unstored = computed(() =>
		Object.entries(changed.value).some(
			([key, value]) =>
				JSON.stringify(value) !== JSON.stringify(settings.stored.value[key as ListSettingsKey])
		)
	);

	async function afterSettingsWrite(write: Promise<void>) {
		await write;
		applyStored();
		readSort();
	}

	const view: View = {
		doctype,
		key: opened.key,
		type: opened.type,
		layer: opened.layer,
		settings: viewSettings,
		filters,
		sort,
		seeded: computed(() => seeded.value),
		modified: computed(
			() =>
				seeded.value &&
				(!sameFilters(filters.value, resolvedFilters()) ||
					!sameSort(sort.value, resolvedSort()) ||
					unstored.value)
		),
		update,
		customized: (key) => settings.has("user", key as ListSettingsKey),
		reset: (key) => afterSettingsWrite(settings.reset(key as ListSettingsKey)),
	};

	return {
		view,
		quickFilterFields,
		customizing,
		metaError: error,
		reloadMeta,
		saveForSite: (value) => afterSettingsWrite(settings.saveForSite(value)),
		resetForSite: (key) => afterSettingsWrite(settings.resetForSite(key)),
		createValues: computed(() => createValues(filters.value, fields.value)),
	};
}
