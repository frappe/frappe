<template>
	<div class="letterhead">
		<div class="mb-4 d-flex justify-content-between">
			<div class="d-flex align-items-center">
				<div
					v-if="letterhead && store.edit_letterhead"
					class="btn-group"
					role="group"
					aria-label="Align Letterhead"
				>
					<button
						v-for="direction in ['Left', 'Center', 'Right']"
						type="button"
						class="btn btn-xs"
						@click="letterhead.align = direction"
						:class="letterhead.align == direction ? 'btn-secondary' : 'btn-default'"
					>
						{{ direction }}
					</button>
				</div>
				<input
					class="ml-4 custom-range"
					v-if="letterhead && store.edit_letterhead"
					type="range"
					name="image-resize"
					min="20"
					:max="range_input_field === 'image_width' ? 700 : 500"
					:value="letterhead[range_input_field]"
					@input="(e) => (letterhead[range_input_field] = parseFloat(e.target.value))"
				/>
			</div>
			<div>
				<button
					class="ml-2 btn btn-default btn-xs"
					v-if="letterhead && store.edit_letterhead"
					@click="upload_image"
				>
					{{ __("Change Image") }}
				</button>
				<button
					v-if="letterhead && store.edit_letterhead"
					class="ml-2 btn btn-default btn-xs btn-change-letterhead"
					@click="change_letterhead"
				>
					{{ __("Change Letter Head") }}
				</button>
				<button
					v-if="letterhead"
					class="ml-2 btn btn-default btn-xs btn-edit"
					@click="toggle_edit_letterhead"
				>
					{{ !store.edit_letterhead ? __("Edit Letter Head") : __("Done") }}
				</button>
				<button
					v-if="!letterhead"
					class="ml-2 btn btn-default btn-xs btn-edit"
					@click="create_letterhead"
				>
					{{ __("Create Letter Head") }}
				</button>
			</div>
		</div>
		<div v-if="letterhead && !store.edit_letterhead" v-html="letterhead.content"></div>
		<!-- <div v-show="letterhead && store.edit_letterhead" ref="editor"></div> -->
		<div
			class="edit-letterhead"
			v-if="letterhead && store.edit_letterhead"
			:style="{
				justifyContent: {
					Left: 'flex-start',
					Center: 'center',
					Right: 'flex-end',
				}[letterhead.align],
			}"
		>
			<div class="edit-image">
				<div v-if="letterhead.image">
					<img
						:src="letterhead.image"
						:style="{
							width:
								range_input_field === 'image_width'
									? letterhead.image_width + 'px'
									: null,
							height:
								range_input_field === 'image_height'
									? letterhead.image_height + 'px'
									: null,
						}"
					/>
				</div>
				<button v-else class="btn btn-default" @click="upload_image">
					{{ __("Upload Image") }}
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { useStore } from "./store";
import { get_image_dimensions } from "./utils";
import { ref, watch, onMounted } from "vue";

// mixin
let { letterhead, store } = useStore();

// variables
let range_input_field = ref(null);
let aspect_ratio = ref(null);
let control = ref(null);
let editor = ref(null);

// methods
function toggle_edit_letterhead() {
	if (store.value.edit_letterhead) {
		store.value.edit_letterhead = false;
		return;
	}
	store.value.edit_letterhead = true;
	if (!control.value) {
		control.value = frappe.ui.form.make_control({
			parent: editor.value,
			df: {
				fieldname: "letterhead",
				fieldtype: "Comment",
				change: () => {
					letterhead.value._dirty = true;
					letterhead.value.content = control.value.get_value();
				},
			},
			render_input: true,
			only_input: true,
			no_wrapper: true,
		});
	}
	control.value.set_value(letterhead.value.content);
}
function change_letterhead() {
	let d = new frappe.ui.Dialog({
		title: __("Change Letter Head"),
		fields: [
			{
				label: __("Letter Head"),
				fieldname: "letterhead",
				fieldtype: "Link",
				options: "Letter Head",
			},
		],
		primary_action: ({ letterhead }) => {
			if (letterhead) {
				set_letterhead(letterhead);
			}
			d.hide();
		},
	});
	d.show();
}
function upload_image() {
	new frappe.ui.FileUploader({
		folder: "Home/Attachments",
		on_success: (file_doc) => {
			get_image_dimensions(file_doc.file_url).then(({ width, height }) => {
				letterhead.value["image"] = file_doc.file_url;
				let new_width = width;
				let new_height = height;
				aspect_ratio.value = width / height;
				range_input_field.value = aspect_ratio.value > 1 ? "image_width" : "image_height";

				if (width > 200) {
					new_width = 200;
					new_height = new_width / aspect_ratio.value;
				}
				if (height > 80) {
					new_height = 80;
					new_width = aspect_ratio.value * new_height;
				}

				letterhead.value["image_height"] = new_height;
				letterhead.value["image_width"] = new_width;
			});
		},
	});
}
function set_letterhead(_letterhead) {
	store.value.change_letterhead(_letterhead).then(() => {
		get_image_dimensions(letterhead.value.image).then(({ width, height }) => {
			aspect_ratio.value = width / height;
			range_input_field.value = aspect_ratio.value > 1 ? "image_width" : "image_height";
		});
	});
}
function create_letterhead() {
	let d = new frappe.ui.Dialog({
		title: __("Create Letter Head"),
		fields: [
			{
				label: __("Letter Head Name"),
				fieldname: "name",
				fieldtype: "Data",
			},
		],
		primary_action: ({ name }) => {
			return frappe.db
				.insert({
					doctype: "Letter Head",
					letter_head_name: name,
					source: "Image",
				})
				.then((doc) => {
					d.hide();
					store.value.change_letterhead(doc.name).then(() => {
						toggle_edit_letterhead();
					});
				});
		},
	});
	d.show();
}
// mounted
onMounted(() => {
	if (!letterhead.value && frappe.boot.sysdefaults.letter_head) {
		set_letterhead(frappe.boot.sysdefaults.letter_head);
	}

	watch(
		() => {
			return letterhead.value ? letterhead.value[range_input_field.value] : null;
		},
		() => {
			if (aspect_ratio.value === null) return;

			let update_field =
				range_input_field.value == "image_width" ? "image_height" : "image_width";
			letterhead.value[update_field] =
				update_field == "image_width"
					? aspect_ratio.value * letterhead.value.image_height
					: letterhead.value.image_width / aspect_ratio.value;
		}
	);
});

// watch
watch(
	letterhead,
	() => {
		if (!letterhead.value) return;
		if (letterhead.value.image_width && letterhead.value.image_height) {
			let dimension =
				letterhead.value.image_width > letterhead.value.image_height ? "width" : "height";
			let dimension_value = letterhead.value["image_" + dimension];
			letterhead.value.content = `
			<div style="text-align: ${letterhead.value.align.toLowerCase()};">
				<img
					src="${letterhead.value.image}"
					alt="${letterhead.value.name}"
					${dimension}="${dimension_value}"
					style="${dimension}: ${dimension_value}px;">
			</div>
		`;
		}
	},
	{ deep: true },
	{ immediate: true }
);
</script>

<style scoped>
.letterhead {
	position: relative;
	border: 1px solid var(--dark-border-color);
	border-radius: var(--border-radius);
	padding: 1rem;
	margin-bottom: 1rem;
}
.edit-letterhead {
	display: flex;
	align-items: center;
}
.edit-image {
	min-width: 40px;
	min-height: 40px;
	border: 1px solid var(--border-color);
}
.edit-image img {
	height: 100%;
}
.edit-title {
	margin-left: 1rem;
	border: 1px solid transparent;
	border-radius: var(--border-radius);
	font-size: var(--text-md);
	font-weight: 600;
}
</style>
