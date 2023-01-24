<template>
	<AppModal
		:openModal="!!openImageModal"
		v-bind="{ size }"
		:backdrop="true"
		:isDraggable="false"
		@cancelClick="cancelClick"
		@primaryClick="primaryClick"
	>
		<template #title
			>Choose {{ openImageModal.is_dynamic ? "Dyanmic Images" : "Static Images" }}</template
		>
		<template #body>
			<div v-if="!openImageModal.is_dynamic" class="modal-body">
				<div class="image-filter">
					<input
						type="search"
						class="form-control input-xs"
						:placeholder="__('Search by filename or extension')"
						v-model="search_text"
						@keydown.stop
						@keyup.stop
						@input="frappe.utils.debounce(searchFile(), 300)"
					/>
				</div>
				<div class="image-file-grid">
					<div
						class="file-wrapper ellipsis"
						v-for="image in images.filter((img) => img)"
						:key="image.name"
						:class="{ 'selected-image': selectedImage == image }"
						@click="handleImageSelect(image)"
					>
						<div class="file-body">
							<div class="file-image">
								<img
									draggable="false"
									:src="image.file_url"
									:alt="image.file_name"
								/>
							</div>
						</div>
						<div class="file-footer">
							<div style="width: 90%">
								<div class="file-title ellipsis">
									{{ frappe.utils.file_name_ellipsis(image.file_name, 40) }}
								</div>
								<div class="file-modified" v-html="get_modified_date(image)"></div>
							</div>
							<span class="fa fa-check-circle icon-show"></span>
						</div>
					</div>
				</div>
			</div>
			<div v-else-if="openImageModal.is_dynamic" class="modal-body">
				<div class="image-file-grid">
					<div
						class="file-wrapper ellipsis"
						v-for="image in MainStore.imageDocFields"
						:key="`${image.parentField && image.parentField + '.'}${image.fieldname}`"
						:class="{ 'selected-image': selectedImage == image }"
						@click="handleImageSelect(image)"
					>
						<div class="file-body">
							<div class="file-image">
								<img
									draggable="false"
									v-if="image.value"
									:src="image.value"
									:alt="image.value"
								/>
								<div class="fallback-image" v-else>
									<div class="content">
										<div
											draggable="false"
											style="margin-bottom: 0.5rem"
											v-html="frappe.utils.icon('image', 'lg')"
										></div>
										<span>Image not Linked</span>
									</div>
								</div>
							</div>
						</div>
						<div class="file-footer">
							<div style="width: 90%">
								<div class="file-title ellipsis">
									{{ frappe.utils.file_name_ellipsis(image.label, 40) }}
								</div>
								<div class="file-modified">
									{{ image.parentField }}
								</div>
								<div class="file-modified">
									{{ image.fieldname }}
								</div>
							</div>
							<span class="fa fa-check-circle icon-show"></span>
						</div>
					</div>
				</div>
			</div>
			<div :ref="refFrappeControl" class="footer-control-container"></div>
		</template>
	</AppModal>
</template>
<script setup>
import { ref, onMounted, watch, nextTick } from "vue";
import { useMainStore } from "../../store/MainStore";
import AppModal from "./AppModal.vue";
import { getMeta, getValue } from "../../store/fetchMetaAndData";
const MainStore = useMainStore();
const props = defineProps(["openImageModal", "updateDynamicTextModal"]);
const search_text = ref("");
const images = ref([]);
const selectedImage = ref(null);

const primaryClick = (e) => {
	if (selectedImage.value) {
		MainStore.dynamicData.push(selectedImage.value);
		MainStore.openImageModal.image = selectedImage.value;
	} else {
		MainStore.openImageModal.image = null;
	}
	MainStore.openImageModal = null;
	MainStore.selectedImage = null;
};
const cancelClick = () => {
	MainStore.openImageModal = null;
	MainStore.selectedImage = null;
};

const handleImageSelect = (image) => {
	if (selectedImage.value == image) {
		selectedImage.value = null;
	} else {
		selectedImage.value = image;
	}
};

const refFrappeControl = (ref) => {
	let imageControl = new frappe.ui.FieldGroup({
		body: $(ref),
		fields: [
			{
				label: __(props.openImageModal.is_dynamic ? "Static Images" : "Dyanmic Images"),
				fieldname: "image_type",
				fieldtype: "Button",
				btn_size: "sm",
				click: () => {
					props.openImageModal.is_dynamic = !props.openImageModal.is_dynamic;
					let image_type = imageControl.fields.find(
						(field) => field.fieldname == "image_type"
					);
					image_type.label = __(
						props.openImageModal.is_dynamic ? "Static Images" : "Dyanmic Images"
					);
					imageControl.fields_dict["upload_image"].wrapper.style.display = props
						.openImageModal.is_dynamic
						? "none"
						: "";
					imageControl.refresh();
				},
			},
			{
				fieldname: "upload_image",
				fieldtype: "Attach Image",
				change: async () => {
					let { upload_image } = imageControl.get_values();
					if (!upload_image) return;
					await searchFile();
					selectedImage.value =
						images.value.find((image) => image.file_url == upload_image) || null;
					imageControl.set_value("upload_image", "");
				},
			},
		],
	});
	imageControl.make();
	imageControl.fields_dict["upload_image"].wrapper.style.display = props.openImageModal
		.is_dynamic
		? "none"
		: "";
	imageControl.refresh();
};

onMounted(async () => {
	if (props.openImageModal) {
		let result = await frappe.db.get_list("File", {
			fields: ["name", "file_name", "file_url", "modified"],
			filters: { is_folder: false },
			order_by: "modified desc",
			limit: 20,
		});
		images.value = result.filter((image) => frappe.utils.is_image_file(image.file_name));
		if (props.openImageModal.image) {
			if (props.openImageModal.is_dynamic) {
				selectedImage.value =
					MainStore.imageDocFields.find(
						(image) => image == props.openImageModal.image
					) || null;
			} else {
				selectedImage.value =
					result.find((image) => image.name == props.openImageModal.image.name) || null;
			}
		}
		if (MainStore.imageDocFields.length) return;
		let imageDocFields = await frappe.call({
			method: "frappe.printing.page.print_designer.print_designer.image_docfields",
			args: {
				doctypes: MainStore.getLinkMetaFields.map((field) => field.options),
			},
		});
		await MainStore.getLinkMetaFields.forEach(async (field) => {
			await imageDocFields.message
				.filter((image) => image.parent == field.options)
				.forEach(async (el) => {
					MainStore.imageDocFields.push({
						name: el.name,
						doctype: field.options,
						fieldname: el.fieldname,
						fieldtype: el.fieldtype,
						label: el.label,
						parentField: field.fieldname,
						value: await getValue(
							field.options,
							MainStore.docData[field.fieldname],
							el.fieldname
						),
					});
				});
		});
		MainStore.imageDocFields.sort((a, b) => a.doctype.localeCompare(b.doctype));
	}
});

const get_modified_date = (file) => {
	const [date] = file.modified.split(" ");
	let modified_on;
	if (date === frappe.datetime.now_date()) {
		modified_on = comment_when(file.modified);
	} else {
		modified_on = frappe.datetime.str_to_user(date);
	}
	return modified_on;
};

const searchFile = async () => {
	if (search_text.value === "" || search_text.value.length < 3) {
		let result = await frappe.db.get_list("File", {
			fields: ["name", "file_name", "file_url", "modified"],
			filters: { is_folder: false },
			order_by: "modified desc",
			limit: 20,
		});
		images.value = result.filter((image) => frappe.utils.is_image_file(image.file_name));
		selectedImage.value &&
			!images.value.find((image) => image.name == selectedImage.value.name) &&
			(images.value = [selectedImage.value, ...images.value]);
		selectedImage.value = result.find((image) => image.name == selectedImage.value?.name);
		return;
	}
	let result = await frappe.call("frappe.core.api.file.get_files_by_search_text", {
		text: search_text.value,
	});
	images.value =
		result.message.filter((image) => frappe.utils.is_image_file(image.file_name)) || [];
	selectedImage.value &&
		!images.value.find((image) => image.name == selectedImage.value.name) &&
		(images.value = [selectedImage.value, ...images.value]);
};

const size = {
	width: "75vw",
	height: "82vh",
	left: "6vw",
	top: "3vh",
};
</script>
<style deep lang="scss">
.modal-body {
	height: 90%;
	overflow: auto;
	background-color: var(--fg-color);
}
.modal-body::-webkit-scrollbar {
	width: 5px;
	height: 5px;
}
.modal-body::-webkit-scrollbar-thumb {
	background: "var(--gray-200)";
	border-radius: 6px;
}
.modal-body::-webkit-scrollbar-track,
.modal-body::-webkit-scrollbar-corner {
	background: var(--fg-color);
}
.icon-show {
	display: none;
}
.image-filter {
	display: flex;
	justify-content: space-around;
	align-items: center;
	margin: 10px;

	button {
		margin-right: 1rem;
	}
}
.footer-control-container {
	position: absolute;
	bottom: 0px;
	background-color: var(--gray-50);
	border-radius: var(--border-radius);
	width: 97%;
	form {
		display: flex;
		align-items: center;
		button {
			margin-left: 10px;
		}
	}
}
.image-file-grid {
	padding: var(--padding-sm);
	display: grid;
	grid-template-rows: repeat(auto-fill, minmax(150px, 1fr));
	grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
	grid-gap: var(--margin-md);
	max-width: 100%;

	.file-wrapper {
		position: relative;
		height: 170px;
		max-height: 170px;
		display: flex;
		justify-content: space-between;
		flex-direction: column;
		width: 100%;
		border: 1px solid var(--border-color);
		border-radius: var(--border-radius);
		text-decoration: none;

		.file-body {
			height: 105px;
			min-height: 105px;
			max-height: 105px;
			display: flex;
			align-items: center;
			flex-direction: row;
			background: var(--bg-color);

			.file-image {
				max-height: 100%;
				display: flex;
				width: 100%;
				min-width: 100%;
			}
		}
		.file-footer {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding: var(--padding-sm);
			background-color: var(--fg-color);
			.file-title {
				font-size: var(--text-md);
				font-weight: 500;
			}
			.file-modified {
				font-size: var(--text-xs);
				word-wrap: break-word;
				color: var(--text-on-gray);
			}
		}
	}
	.file-wrapper:hover {
		img {
			filter: opacity(75%);
		}
	}
	.selected-image {
		border: 1px solid var(--success);
		border-radius: var(--border-radius);

		.icon-show {
			display: unset;
			font-size: 0.9rem;
			color: var(--success);
		}
	}
}
.fallback-image {
	width: 100%;
	user-select: none;
	height: 100%;
	display: flex;
	word-wrap: break-word;
	align-items: center;
	justify-content: center;
	background-color: var(--bg-color);
	.content {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;

		span {
			font-size: smaller;
			text-align: center;
		}
	}
}
</style>
