<template>
	<button
		ref="dropdown_btn_ref"
		class="dropdown-btn btn btn-xs btn-icon"
		@click.stop="toggle_fieldtype_options"
	>
		<slot>
			<div v-html="frappe.utils.icon('dot-horizontal', 'sm')" />
		</slot>
		<Teleport to="#autocomplete-area">
			<div class="dropdown" ref="dropdown_ref">
				<div v-show="show" class="dropdown-options">
					<div v-for="group in groups" :key="group.key" class="groups">
						<div v-if="group.group" class="group-title">
							{{ __(group.group) }}
						</div>
						<div
							class="dropdown-option"
							v-for="item in group.items"
							:key="item.label"
							:title="item.tooltip"
						>
							<button class="dropdown-item" @click.stop="action(item.onClick)">
								{{ __(item.label) }}
							</button>
						</div>
					</div>
				</div>
			</div>
		</Teleport>
	</button>
</template>

<script setup>
import { createPopper } from "@popperjs/core";
import { nextTick, ref, computed } from "vue";
import { onClickOutside } from "@vueuse/core";

const props = defineProps({
	options: {
		type: Array,
		required: true,
	},
	placement: {
		type: String,
		default: "bottom-end",
	},
});

const show = ref(false);

const dropdown_btn_ref = ref(null);
const dropdown_ref = ref(null);
const popper = ref(null);

onClickOutside(dropdown_btn_ref, () => (show.value = false), { ignore: [dropdown_ref] });

const groups = computed(() => {
	let _groups = props.options[0]?.group ? props.options : [{ group: "", items: props.options }];

	return _groups.map((group, i) => {
		return {
			key: i,
			group: group.group,
			items: group.items,
		};
	});
});

function setupPopper() {
	if (!popper.value) {
		popper.value = createPopper(dropdown_btn_ref.value, dropdown_ref.value, {
			placement: props.placement,
			modifiers: [
				{
					name: "offset",
					options: {
						offset: [0, 4],
					},
				},
			],
		});
	} else {
		popper.value.update();
	}
}

function toggle_fieldtype_options() {
	show.value = !show.value;
	nextTick(() => setupPopper());
}

function action(clickEvent) {
	clickEvent && clickEvent();
	show.value = false;
}
</script>

<style lang="scss" scoped>
.groups {
	padding: 5px;

	.group-title {
		display: flex;
		align-items: center;
		padding: 4px 8px;
		font-size: smaller;
		font-weight: 600;
		text-transform: uppercase;
		color: var(--disabled-text-color);
	}
}

.dropdown-btn {
	&:hover {
		background-color: var(--bg-light-gray);
	}
}
.dropdown-options {
	background-color: var(--fg-color);
	border-radius: var(--border-radius-lg);
	box-shadow: var(--shadow-2xl);
	padding: 4px;
	border: 1px solid var(--subtle-accent);
}
.dropdown {
	z-index: 100;
}
</style>
