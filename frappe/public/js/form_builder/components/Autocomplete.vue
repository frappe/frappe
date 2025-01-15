<template>
	<Combobox v-model="selectedValue" nullable>
		<ComboboxOptions class="combo-box-options" static>
			<div class="search-box">
				<ComboboxInput
					ref="search"
					class="search-input form-control"
					type="text"
					@change="(e) => (query = e.target.value)"
					:value="query"
					:placeholder="__(props.placeholder)"
					autocomplete="off"
					@click.stop
				/>
				<button class="clear-button btn btn-sm" @click="clear_search">
					<div v-html="frappe.utils.icon('close', 'sm')" />
				</button>
			</div>
			<div class="combo-box-items">
				<ComboboxOption
					as="template"
					v-for="(field, i) in sortedOptions"
					:key="i"
					:value="field"
					v-slot="{ active }"
				>
					<li :class="['combo-box-option', active ? 'active' : '']">
						{{ __(field.label) }}
					</li>
				</ComboboxOption>
			</div>
		</ComboboxOptions>
	</Combobox>
</template>

<script setup>
import { Combobox, ComboboxInput, ComboboxOptions, ComboboxOption } from "@headlessui/vue";
import { computed, ref, useAttrs, watch, nextTick } from "vue";

const props = defineProps({
	options: {
		type: Array,
		default: [],
	},
	placeholder: {
		type: String,
		default: "",
	},
	modelValue: {
		type: String,
		default: "",
	},
	show: {
		type: Boolean,
		default: false,
	},
});

const emit = defineEmits(["update:modelValue", "update:show", "change"]);
const attrs = useAttrs();

const query = ref(null);
const search = ref(null);

const showOptions = computed({
	get() {
		return props.show;
	},
	set(val) {
		emit("update:show", val);
	},
});

const selectedValue = computed({
	get() {
		return attrs.value;
	},
	set(val) {
		query.value = "";
		if (val) {
			showOptions.value = false;
		}
		emit("change", val);
	},
});

const filteredOptions = computed(() => {
	if (!query.value) return props.options;
	return props.options.filter((option) => {
		return option.label.toLocaleLowerCase().includes(query.value.toLocaleLowerCase());
	});
});

const sortedOptions = computed(() => {
	return filteredOptions.value.sort((a, b) => {
		return a.label.localeCompare(b.label);
	});
});

function clear_search() {
	selectedValue.value = "";
	search.value.el.focus();
}

watch(showOptions, (val) => {
	if (val) {
		nextTick(() => {
			search.value.el.focus();
		});
	}
});
</script>

<style lang="scss" scoped>
.combo-box {
	z-index: 100;
}

.combo-box-options {
	width: 100%;
	background-color: var(--fg-color);
	border-radius: var(--border-radius-lg);
	box-shadow: var(--shadow-2xl);
	padding: 0;
	border: 1px solid var(--subtle-accent);
}

.combo-box-option {
	font-size: small;
	text-align: left;
	border-radius: var(--border-radius-sm);
	padding: 6px 10px;
	width: 100%;
	cursor: pointer;
	user-select: none;

	&:hover,
	&.active {
		background-color: var(--bg-light-gray);
	}
}

.combo-box-items {
	max-height: 200px;
	padding: 5px;
	padding-top: 0px;
	overflow-y: auto;
}

.search-box {
	position: relative;
	padding: 6px;
	.clear-button {
		position: absolute;
		right: 0;
		top: 0;
		bottom: 0;
		display: inline-flex;
		justify-content: center;
		align-items: center;
		cursor: pointer;
	}
	.search-input {
		width: 100%;
	}
}
</style>
