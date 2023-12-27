<script setup>
import {
	computed,
	provide,
	inject,
	ref,
	shallowRef,
	markRaw,
	watch,
	onMounted,
	onUnmounted,
} from "vue";
import { with_doctype } from "./link_catalog_common";
import VueSmartElement from "./VueSmartElement.vue";

// Props
const props = defineProps({
	doc: {
		type: Object,
		required: true,
	},
});

// Injected

/** @type {import('./link_catalog_common').CatalogOptions} */
const options = inject("options");

/** @type {import('./link_catalog_common').Bus} */
const bus = inject("bus");

/** @type {import('./LinkCatalogAdapter').BaseLayoutAdapter} */
const layoutAdapter = inject("layoutAdapter");

// Provide

provide("item", props.doc);

// State
const state = ref("loading");
const meta = shallowRef(null);
const spec = shallowRef(null);
const quantity = ref(0);

const href = computed(() => {
	return frappe.utils.get_form_link(props.doc.doctype, props.doc.name);
});

// Listen to the refresh event
let off = null;
onMounted(() => {
	off = bus.on("refresh", refreshQuantity);
});
onUnmounted(() => {
	off?.();
});

watch(
	() => props.doc.doctype,
	async () => {
		state.value = "loading";
		await with_doctype(props.doc.doctype);
		meta.value = frappe.get_meta(props.doc.doctype);
		spec.value = getSpec();
		refreshQuantity();
		state.value = "loaded";
	},
	{ immediate: true }
);

function getSpec() {
	const image_field = meta.value.image_field || null;
	const title_field = meta.value.title_field || null;

	return {
		image_field,
		title_field,
	};
}

// Event handlers

function plus() {
	setQuantity(quantity.value + 1);
}

function minus() {
	setQuantity(quantity.value - 1);
}

function setQuantity(qty) {
	qty = Math.max(0, Number(qty));
	quantity.value = qty;
	bus.emit("selectItem", {
		selected: props.doc,
		quantity: qty,
		// callback: qty && refreshQuantity,
	});
}

function refreshQuantity() {
	quantity.value = layoutAdapter.grab_quantity(props.doc);
}

// Utilities

function get_df(fieldname) {
	const df = frappe.meta.get_docfield(props.doc.doctype, fieldname);
	if (!df) {
		throw new Error(`Invalid fieldname: ${fieldname}`);
	}
	return df;
}

function format(field) {
	if (!frappe.get_meta(props.doc?.doctype)) {
		return "Ensure component is running in Suspense context";
	}

	let df = null;
	if (typeof field === "string") {
		df = get_df(field);
	} else if (field?.fieldtype) {
		df = field;
	} else {
		throw new Error("Invalid field");
	}

	if (!df) {
		return "";
	}

	const value = props.doc[df.fieldname];
	return frappe.format(value, df, null, props.doc);
}
</script>

<template>
	<article class="LinkCatalogItem" :class="{ 'LinkCatalogItem--selected': quantity > 0 }">
		<template v-if="state === 'loading'">
			<i class="fa fa-spinner fa-spin"></i>
		</template>
		<template v-else>
			<template v-if="spec.image_field && doc[spec.image_field]">
				<a class="LinkCatalogItem__image" :href="doc[spec.image_field]" target="_blank">
					<img :src="doc[spec.image_field]" alt="" />
				</a>
			</template>

			<header class="user-select-none">
				<h3>
					<a :href="href" target="_blank">
						{{ spec.title_field ? format(spec.title_field) : doc.name }}
					</a>
				</h3>
			</header>

			<div style="grid-area: body">
				<VueSmartElement :element="markRaw(options.item_contents || [])" />
			</div>

			<footer>
				<VueSmartElement :element="markRaw(options.item_footer || [])" />

				<div class="LinkCatalogItem__buttons">
					<div class="btn-group" v-if="options.quantity_fieldname">
						<button
							class="btn btn-md btn-text-default LinkCatalogItem__decrement"
							type="button"
							:aria-label="__('Remove')"
							@click="minus"
							v-html="frappe.utils.icon('es-line-dash')"
						/>
						<input
							class="btn-reset input-xs font-weight-bold LinkCatalogItem__quantity"
							type="number"
							inputmode="numeric"
							min="0"
							:value="quantity"
							:aria-label="__('Quantity')"
							@change="($e) => setQuantity($e.target.value)"
							@focus="($e) => $e.target.select()"
						/>
						<button
							class="btn btn-md btn-text-default LinkCatalogItem__increment"
							type="button"
							:aria-label="__('Add')"
							@click="plus"
							v-html="frappe.utils.icon('es-line-add')"
						/>
					</div>
					<button
						v-else-if="quantity > 0"
						class="btn btn-md btn-text-default"
						type="button"
						@click="setQuantity(0)"
					>
						Remove
					</button>
					<button
						v-else
						class="btn btn-md btn-text-default"
						type="button"
						@click="setQuantity(1)"
					>
						Add
					</button>
				</div>
			</footer>
		</template>
	</article>
</template>

<style lang="scss">
.LinkCatalogItem {
	display: grid;
	grid-template-areas:
		"image header"
		"image body"
		"footer footer";
	grid-template-columns: 1fr 2fr;
	grid-template-rows: auto 1fr auto;
	gap: 0px;

	border-radius: var(--border-radius);
	word-break: break-word;
	/* text-wrap: balance; */

	box-shadow: 0 0 0 1px var(--border-color);

	&:not(:hover, :focus-visible, :focus-within, .LinkCatalogItem--selected) {
		.LinkCatalogItem__buttons {
			opacity: 0.5;
		}
	}

	&:not(:has(.LinkCatalogItem__image)) {
		grid-template-columns: 0px 1fr;
	}

	&--selected {
		box-shadow: 0 0 0 2px var(--text-muted);
	}

	& > header {
		grid-area: header;
		display: flex;
		align-items: center;
		padding: 0.5em;
	}

	& > header > h3 {
		margin: 0;
		font-size: var(--text-lg);
		font-weight: var(--weight-bold);
	}

	& > &__image {
		grid-area: image;
		padding: 0.25em;

		& > img {
			/* width: 100%;
			height: 100%; */
			object-fit: contain;
			transition: all 0.2s ease;
			transition-property: transform, box-shadow, background-color;
			max-height: 64px;

			&:hover {
				transform: scale(3);
				z-index: 100;
				cursor: zoom-in;
				box-shadow: var(--shadow-2xl);
				background-color: var(--fg-color);
			}
		}
	}

	& > dl {
		grid-area: body;
		padding: 0 0.5em;
		display: flex;
		flex-direction: column;
		gap: 0.125em;
		font-size: var(--text-sm);

		:is(dt, dd) {
			display: inline;
			margin: 0;
			font-weight: var(--weight-normal);
		}
		dd {
			font-weight: var(--weight-semibold);
		}
	}

	& > footer {
		margin-top: auto;
		grid-area: footer;
		display: flex;
		justify-content: flex-end;
		// background-color: var(--bg-color);

		.btn {
			font-size: var(--text-xs);
		}
	}

	.LinkCatalogItem__quantity {
		text-align: center;
		width: 2.5em;

		// https://www.w3schools.com/howto/howto_css_hide_arrow_number.asp
		/* Firefox */
		-moz-appearance: textfield;

		/* Chrome, Safari, Edge, Opera */
		&::-webkit-outer-spin-button,
		&::-webkit-inner-spin-button {
			-webkit-appearance: none;
			margin: 0;
		}
	}
}
</style>
