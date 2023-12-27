<script setup>
// @ts-check
import { watch, shallowRef, ref, inject, onMounted, markRaw } from "vue";
import { with_doctype } from "./link_catalog_common";
import LinkCatalogItem from "./LinkCatalogItem.vue";
import VueSmartElement from "./VueSmartElement.vue";
import FrappeFilters from "./FrappeFilters.vue";

const options = inject("options");
const bus = inject("bus");
const layoutAdapter = inject("layoutAdapter");

const results = shallowRef([]);

/** @type {import('vue').Ref<Array>} */
const filters = ref([]);

/** @type {import('vue').Ref<Array>} */
const or_filters = ref([]);

const search = ref("");
const page_index = ref(0);
const page_length = ref(50);

/** @type {import('vue').Ref<HTMLInputElement | null>} */
const searchInput = ref(null);

// Watchers
watch(
	[filters, or_filters, page_index, page_length],
	async () => {
		results.value = await doSearch();
	},
	{ immediate: true }
);

watch(search, (value) => {
	// Remove old search filters
	const searchFilters = [];
	if (value) {
		for (const fieldname of options.search_fields || ["name"]) {
			searchFilters.push([options.link_doctype, fieldname, "like", `%${value}%`]);
		}
	}
	or_filters.value = searchFilters;
});

onMounted(() => {
	searchInput.value?.focus();

	bus.on("selectItem", async ({ selected, quantity, callback }) => {
		await setQuantity(selected, quantity);
		if (typeof callback === "function") {
			callback();
		}
	});

	bus.on("setFilters", (newFilters) => {
		filters.value = newFilters;
	});
});

// Functions
async function doSearch() {
	const limit_page_length = page_length.value;
	const limit_start = page_index.value * page_length.value;

	const args = {
		filters: filters.value,
		or_filters: or_filters.value,
		limit_page_length,
		limit_start,
	};

	if (typeof options.search_function === "function") {
		return await options.search_function({ search, ...args });
	}

	await with_doctype(options.link_doctype);
	const meta = frappe.get_meta(options.link_doctype);
	const fields = new Set(["name", meta.title_field || "name", meta.image_field || null]);
	const res = await frappe.db.get_list(options.link_doctype, { fields: [...fields], ...args });
	for (const doc of res) {
		doc.doctype = options.link_doctype;
	}
	return res;
}

async function setQuantity(selected, newQuantity = 1) {
	if (newQuantity > 0) {
		const values = {};
		if (options.link_fieldname) {
			values[options.link_fieldname] = selected.name;
		}
		if (options.quantity_fieldname) {
			values[options.quantity_fieldname] = newQuantity;
		}
		await layoutAdapter.upsert(selected, values);
	} else {
		await layoutAdapter.remove(selected);
	}
}
</script>

<template>
	<section class="LinkCatalog">
		<nav role="navigation" aria-label="Sidebar">
			<VueSmartElement
				v-if="options.title && typeof options.title == 'object'"
				:element="markRaw(options.title)"
			/>
			<h2 v-else-if="options.title">{{ options.title }}</h2>

			<form role="search">
				<label for="LinkCatalog__search-input" class="LinkCatalog__search-input">
					<input
						id="LinkCatalog__search-input"
						class="form-control"
						type="search"
						autocomplete="off"
						v-model="search"
						ref="searchInput"
						:placeholder="__('Search...')"
						:aria-label="__('Type something in the search box to search')"
					/>
					<span v-html="frappe.utils.icon('es-line-search')" />
				</label>
				<button type="submit" class="sr-only">{{ __("Search") }}</button>
			</form>

			<VueSmartElement :element="markRaw(options.sidebar_contents || [])" />

			<FrappeFilters class="mt-4" v-model="filters" :doctype="options.link_doctype" />
		</nav>

		<main>
			<LinkCatalogItem :doc="doc" v-for="doc in results" :key="doc.name" />
		</main>
	</section>
</template>

<style>
.LinkCatalog {
	display: flex;
	flex-direction: row;
	align-items: flex-start;
	gap: 1.4em;
}

.LinkCatalog > nav {
	flex: 0 0 250px;
}

.LinkCatalog > main {
	flex: 1 0 0;

	/* Fallback */
	display: flex;
	flex-direction: column;

	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
	grid-template-rows: 1fr;
	align-items: stretch;
	justify-items: stretch;
	gap: 1.4em;
}

.LinkCatalog__search-input {
	position: relative;
}
.LinkCatalog__search-input > span {
	position: absolute;
	inset-inline-end: 8px;
	inset-block: 0;
	display: flex;
	align-items: center;
}
</style>
