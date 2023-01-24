<template>
	<AppModal
		:openModal="!!openDyanmicModal"
		v-bind="{ size }"
		:backdrop="true"
		:isDraggable="false"
		@cancelClick="cancelClick"
		@primaryClick="primaryClick"
	>
		<template #title>Dynamic Text</template>
		<template #body>
			<div>
				<div class="dynamic-results flex">
					<div class="col-md-2 col-sm-2 dynamic-side-section">
						<ul class="list-unstyled dynamic-sidebar">
							<li
								class="dynamic-sidebar-item"
								:class="{
									'dynamic-sidebar-item-selected': parentField == '',
								}"
								@click="parentField = ''"
							>
								<span>{{ MainStore.doctype }}</span>
							</li>
							<li
								v-for="field in MainStore.getLinkMetaFields"
								@click="handleSidebarClick(field.fieldname)"
								:fieldtype="field.fieldname"
								:value="field.fieldname"
								class="dynamic-sidebar-item dynamic-sidebar-item"
								:class="{
									'dynamic-sidebar-item-selected':
										parentField == field.fieldname,
								}"
							>
								<span>{{ field.label }}</span>
							</li>
						</ul>
					</div>
					<div class="col-md-10 col-sm-10 results-area">
						<div class="results-summary col-sm-12">
							<div class="col-sm-12 result-section row">
								<div class="result-body col-sm-4">
									<div
										class="result"
										v-if="!doctype"
										@click="
											selectField(
												{
													fieldname: 'name',
													fieldtype: 'Small Text',
													label: 'Name',
													options: undefined,
												},
												'Small Text'
											)
										"
										:class="{
											'result-selected': fieldnames.filter(
												(el) =>
													el.parentField == '' && el.fieldname == 'name'
											).length,
										}"
									>
										<div class="col-sm-12 result-text">
											<span class="result-section-link">{{ "Name" }}</span>
											<span class="fa fa-check-circle icon-show"></span>
										</div>
									</div>
								</div>
							</div>
							<div
								class="col-sm-12 result-section row"
								v-for="(fields, fieldtype) in MainStore.getTypeWiseMetaFields(
									parentField
								)"
								:data-type="fieldtype"
								:key="fieldtype"
							>
								<div class="result-title col-sm-12">
									{{ fieldtype }}
								</div>
								<div
									class="result-body col-sm-4"
									v-for="field in fields"
									:key="field.fieldname"
									:value="field.fieldname"
								>
									<div
										class="result"
										@click="selectField(field, fieldtype)"
										:class="{
											'result-selected': fieldnames.filter(
												(el) =>
													el.parentField == parentField &&
													el.fieldname == field.fieldname
											).length,
										}"
									>
										<div class="col-sm-12 result-text">
											<span class="result-section-link">{{
												field.label || field.fieldname
											}}</span>
											<span class="fa fa-check-circle icon-show"></span>
										</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
			<div
				class="col-12 dynamic-preview-container"
				@drop.self="drop($event, fieldnames.length)"
				@dragover="allowDrop"
				@click.self.stop="selectedEl = null"
			>
				<template v-for="(field, index) in fieldnames" :key="index">
					<div
						class="dynamic-field"
						:class="{
							'static-text': field.fieldtype == 'StaticText',
							'static-text-selected':
								field.fieldtype == 'StaticText' && selectedEl?.index == index,
							'dynamic-field-selected':
								field.fieldtype != 'StaticText' && selectedEl?.index == index,
						}"
						:fieldtype="`${field.parentField ? field.parentField + '__' : ''}${
							field.fieldname
						}`"
						:value="field.fieldname"
						:id="`${field.parentField ? field.parentField + '__' : ''}${
							field.fieldname
						}`"
						style="width: fit-content"
						draggable="true"
						@click.stop="handleClick($event, field, index)"
						@dragstart="dragstart($event, index)"
						@drop="drop($event, index)"
						@dragleave="dragleave"
						@dragover="allowDrop"
					>
						<span
							v-if="!field.is_static && field.is_labelled"
							:ref="(e) => (field.labelRef = e)"
							class="label-text dyanmic-text"
							:class="{
								'label-text-selected': selectedEl?.index == index,
							}"
							:contenteditable="contenteditable"
							@keydown.stop
							@keyup.stop
							@dblclick="handleDblClick($event, field)"
							@blur="handleBlur($event, field)"
							v-html="
								`${field.label}` ||
								`{{ ${field.parentField ? field.parentField + '.' : ''}${
									field.fieldname
								} }}`
							"
						></span>
						<span
							:ref="(e) => (field.spanRef = e)"
							class="result-section-link"
							:class="{ 'result-section-selected': selectedEl?.index == index }"
							style="padding: 0; padding-left: 2px"
							:contenteditable="contenteditable"
							@keydown.stop
							@keyup.stop
							@dblclick="handleDblClick($event, field)"
							@blur="handleBlur($event, field)"
							v-html="
								field.value ||
								(field.is_static
									? 'Add Text'
									: `{{ ${field.parentField ? field.parentField + '.' : ''}${
											field.fieldname
									  } }}`)
							"
						></span>
						<span
							v-if="field.nextLine"
							class="mx-2 fa fa-level-down"
							data-v-b41cc414=""
							style="color: var(--text-light)"
						></span>
					</div>
					<br v-if="field.nextLine" />
				</template>
			</div>
			<div class="dynamic-modal-footer">
				<div class="staticTextIcon">
					<div @click="addStaticText">
						<em style="font-weight: 900">T</em>
						<sub style="font-weight: 600; font-size: 1em bottom:-0.15em">+</sub>
						<!-- <span class="fa fa-font"></span> -->
					</div>
					<div v-if="selectedEl" id="add-label" @click="handleAddLabel">
						<span
							class="ml-2 fa fa-tag"
							style="background-color: transparent"
							:style="[selectedEl.field.is_labelled && 'color:var(--primary)']"
						></span>
					</div>
					<div v-if="selectedEl" @click="handleAddNextLine($event, selectedEl.field)">
						<span
							class="ml-2 fa fa-level-down"
							style="color: var(--text-dark)"
							:style="[selectedEl.field.nextLine && 'color:var(--primary)']"
						></span>
					</div>
				</div>
				<div class="help-legend-container">
					<div class="legend">
						<div>
							<span class="fa fa-square" style="color: var(--primary)"></span
							><span> Editable Text</span>
						</div>
						<div>
							<span class="fa fa-square" style="color: var(--success)"></span
							><span> Dynamic Text</span>
						</div>
					</div>
				</div>
				<div
					class="deleteIcon"
					v-if="fieldnames.length"
					@dragleave="dragleave"
					@dragover="allowDeleteDrop"
					@drop="(ev) => deleteField(ev)"
					@click.stop="handleDeleteClick"
				>
					<span class="fa fa-trash"></span>
				</div>
			</div>
		</template>
	</AppModal>
</template>
<script setup>
import { ref, onMounted, watch, nextTick } from "vue";
import { getMeta, getValue } from "../../store/fetchMetaAndData";
import { useMainStore } from "../../store/MainStore";
import AppModal from "./AppModal.vue";
const MainStore = useMainStore();

const props = defineProps(["openDyanmicModal", "updateDynamicTextModal"]);
const doctype = ref("");
const parentField = ref("");
const fieldnames = ref([]);
const contenteditable = ref(false);
const selectedEl = ref(null);
const draggableEl = ref(-1);

watch(parentField, () => {
	if (!parentField.value) {
		doctype.value = "";
	} else {
		let meta = MainStore.metaFields.find((field) => field.fieldname == parentField.value);
		if (!meta.childfields) {
			getMeta(meta.options, parentField.value);
		}
		doctype.value = meta.options;
	}
});

onMounted(() => {
	if (props.openDyanmicModal) {
		fieldnames.value = props.openDyanmicModal.dynamicContent;
	}
});

const size = {
	width: "75vw",
	height: "82vh",
	left: "6vw",
	top: "3vh",
};

const handleSidebarClick = async (fieldname) => {
	let meta = MainStore.metaFields.find((field) => field.fieldname == fieldname);
	if (!meta.childfields) {
		await getMeta(meta.options, fieldname);
	}
	parentField.value = fieldname;
};

const handleAddNextLine = (event, field) => {
	field.nextLine = !field?.nextLine;
};

const selectElementContents = (el) => {
	const range = document.createRange();
	range.selectNodeContents(el);
	const sel = window.getSelection();
	sel.removeAllRanges();
	sel.addRange(range);
};
const addStaticText = (event) => {
	let index = fieldnames.value.length;
	let newText = {
		doctype: "",
		parentField: "",
		fieldname: frappe.utils.get_random(10),
		value: "Add Text",
		fieldtype: "StaticText",
		is_static: true,
		is_labelled: false,
	};
	if (selectedEl.value) {
		index = selectedEl.value.index + 1;
		fieldnames.value.splice(index, 0, newText);
	} else {
		fieldnames.value.push(newText);
	}
	contenteditable.value = true;
	nextTick(() => {
		fieldnames.value.at(index).spanRef.focus();
		selectElementContents(fieldnames.value.at(index).spanRef);
		selectedEl.value = { index, field: newText };
	});
};

const handleClick = (event, field, index) => {
	selectedEl.value = { index, field };
	parentField.value = field.parentField;
};
const handleAddLabel = (event) => {
	selectedEl.value.field.is_labelled = !selectedEl.value.field.is_labelled;
};

const handleBlur = (event, field) => {
	contenteditable.value = false;
	if (event.target == field.spanRef) {
		field.value = event.target.innerHTML;
	} else {
		field.label = event.target.innerHTML;
	}
};
const handleDblClick = (event, field) => {
	if (field.fieldtype != "StaticText" && !field.is_labelled) return;
	contenteditable.value = true;
	setTimeout(() => {
		event.target.focus();
		selectElementContents(field.labelRef || field.spanRef);
	}, 0);
};

const allowDrop = (ev) => {
	ev.dataTransfer.dropEffect = "move";
	ev.target.classList.contains("dynamic-field") || ev.target.classList.contains("deleteIcon")
		? ev.target.classList.add("dropzone")
		: ev.target.parentElement.classList.add("dropzone");
	ev.preventDefault();
};
const allowDeleteDrop = (ev) => {
	ev.dataTransfer.dropEffect = "move";
	ev.target.classList.contains("dynamic-field") || ev.target.classList.contains("deleteIcon")
		? ev.target.classList.add("dropzone")
		: ev.target.parentElement.classList.add("dropzone");
	ev.preventDefault();
};
const dragstart = (ev, index) => {
	ev.dataTransfer.dropEffect = "move";
	draggableEl.value = index;
};
const dragleave = (ev) => {
	ev.target.classList.contains("dynamic-field") || ev.target.classList.contains("deleteIcon")
		? ev.target.classList.remove("dropzone")
		: ev.target.parentElement.classList.remove("dropzone");
};

const deleteField = (ev) => {
	ev.target.classList.contains("dynamic-field") || ev.target.classList.contains("deleteIcon")
		? ev.target.classList.remove("dropzone")
		: ev.target.parentElement.classList.remove("dropzone");
	fieldnames.value.splice(draggableEl.value, 1);
	if (draggableEl.value == selectedEl.value?.index) {
		selectedEl.value = null;
	}
	draggableEl.value = -1;
};

const handleDeleteClick = () => {
	if (selectedEl.value) {
		fieldnames.value.splice(selectedEl.value.index, 1);
		selectedEl.value = null;
	}
};

const drop = (ev, index) => {
	ev.target.classList.contains("dynamic-field") || ev.target.classList.contains("deleteIcon")
		? ev.target.classList.remove("dropzone")
		: ev.target.parentElement.classList.remove("dropzone");
	let dragField = fieldnames.value.splice(draggableEl.value, 1);
	fieldnames.value.splice(index, 0, dragField[0]);
	ev.preventDefault();
	selectedEl.value = null;
};
const selectField = async (field, fieldtype) => {
	let isRemoved = false;
	fieldnames.value = fieldnames.value.filter((el) => {
		if (el.parentField == parentField.value && el.fieldname == field.fieldname) {
			isRemoved = true;
			return false;
		}
		return true;
	});
	if (!isRemoved) {
		let index = fieldnames.value.length;
		let value = parentField.value
			? MainStore.docData[parentField.value]
				? await getValue(
						doctype.value,
						MainStore.docData[parentField.value],
						field.fieldname
				  )
				: `{{ ${parentField.value}.${field.fieldname} }}`
			: MainStore.docData[field.fieldname];
		let dynamicFeild = {
			doctype: doctype.value,
			parentField: parentField.value,
			fieldname: field.fieldname,
			value,
			fieldtype,
			label: `<b> ${field.label} : </b>`,
			is_labelled: false,
			is_static: false,
		};
		if (selectedEl.value) {
			index = selectedEl.value.index + 1;
			fieldnames.value.splice(index, 0, dynamicFeild);
			MainStore.dynamicData.splice(index, 0, dynamicFeild);
		} else {
			fieldnames.value.push(dynamicFeild);
			MainStore.dynamicData.push(dynamicFeild);
		}
		selectedEl.value = { index, field: dynamicFeild };
	}
};

const primaryClick = (e) => {
	MainStore.openDyanmicModal.dynamicContent = fieldnames.value;
	props.openDyanmicModal.selectedDyanmicText = [];
	MainStore.openDyanmicModal = null;
	nextTick(() => {
		fieldnames.value.forEach((el) => {
			delete el["spanRef"];
			delete el["labelRef"];
		});
	});
};
const cancelClick = () => {
	props.openDyanmicModal.selectedDyanmicText = [];
	MainStore.openDyanmicModal = null;
};
</script>
<style scoped lang="scss">
.label-text {
	padding: 6px 1px;
	margin: 0px 3px;
}
.label-text:hover,
.label-text-selected {
	border: 1px solid var(--primary);
	padding: 6px 1px;
	margin: 0px 2px;
	border-radius: var(--border-radius);
}
.dynamic-field {
	display: inline-block;
	box-sizing: border-box;
	padding: 8px 1px;
	color: var(--text-light);
}
.dynamic-field:hover,
.dynamic-field-selected {
	border: 1px solid var(--success);
	padding: 7px 0;
	border-radius: var(--border-radius);
}
.static-text:hover,
.static-text-selected {
	border: 1px solid var(--primary);
	padding: 7px 0;
	border-radius: var(--border-radius);
}
.dynamic-preview-container {
	border: 1px solid var(--gray-200);
	border-radius: var(--border-radius);
	height: calc(23vh - 45px);
	width: 100%;
	background-color: var(--bg-color);
	overflow: auto;
	margin-top: 15px;
}
.result {
	display: flex;
	align-items: center;
	padding: 8px 0;
	margin: 0px 8px;
	color: var(--text-light);
}
.results-area {
	max-height: min(55vh, 650px);
	overflow: auto;
}
.results-area::-webkit-scrollbar,
.dynamic-sidebar::-webkit-scrollbar {
	width: 5px;
	height: 5px;
}
.results-area::-webkit-scrollbar-thumb,
.dynamic-sidebar::-webkit-scrollbar-thumb {
	background: "var(--gray-200)";
	border-radius: 6px;
}
.results-area {
	max-height: min(55vh, 650px);
	overflow: auto;
}
.results-area::-webkit-scrollbar-track,
.results-area::-webkit-scrollbar-corner {
	background: white;
}
.dynamic-sidebar::-webkit-scrollbar-track,
.dynamic-sidebar::-webkit-scrollbar-corner {
	background: var(--bg-color);
}
.dynamic-side-section {
	background-color: var(--bg-color);
	overflow: hidden;
	padding-right: 0px;
	padding-left: 0px;
}
.result-body {
	font-size: var(--text-md);
	padding: var(--padding-sm) 0;
	border-bottom: 1px solid var(--border-color);
}
.modal-dialog .dynamic-results .results-summary {
	padding-top: var(--padding-sm);
}
.modal-dialog .dynamic-results {
	max-height: min(55vh, 650px);
	.dynamic-sidebar {
		max-height: min(55vh, 650px);
		position: sticky;
		top: 0;
		overflow-y: auto;
		padding-bottom: var(--padding-md);
	}
}

.dynamic-sidebar-item {
	display: flex;
	align-items: center;
	font-size: 0.75rem;
	margin-bottom: 2px;
	border-radius: var(--border-radius-md);
	overflow: hidden;
	cursor: pointer;

	span {
		padding: 8px 1px 8px 5px;
		margin-left: 3px;
	}
}
.dynamic-sidebar-item:hover,
.dynamic-sidebar-item-selected {
	border: 1px solid var(--gray-300);
	span {
		padding: 7px 0px 7px 4px;
	}
	background-color: white;
}
.dropzone {
	background-color: var(--gray-200);
}

.result-title {
	display: flex;
	font-size: 1.25em;
	font-weight: bolder;
	padding: 6px 0px;
	margin-left: 0;
}
.result:hover,
.result-selected {
	border: 1px solid var(--success);
	padding: 7px 0px;
	border-radius: var(--border-radius);

	.result-text {
		padding: 0px 14px;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
}
.result-section-link:hover,
.result-section-selected {
	color: var(--dark);
}
.result-title:not(:first-child) {
	padding-top: 1em;
}
.icon-show {
	display: none;
}
.result-selected {
	font-weight: 600;
	.icon-show {
		display: unset;
		color: var(--success);
	}
}
.deleteIcon {
	display: flex;
	flex: 1;
	max-width: 24px;
	align-items: center;
	font-size: medium;
	justify-content: center;
	padding: 10px 20px;
	color: var(--danger);
}
.dynamic-modal-footer {
	display: flex;
	align-items: center;
	justify-content: space-evenly;
}
.help-legend-container {
	flex: auto;
	display: flex;
	font-size: small;
	justify-content: flex-start;
	align-items: center;
	padding-left: 24px;
}
.legend {
	display: flex;
	justify-content: space-around;
	align-items: center;
	span {
		padding-left: 10px;
	}
}
.staticTextIcon {
	display: flex;
	max-width: 100px;
	flex: 1;
	align-items: center;
	font-size: medium;
	justify-content: flex-start;
	padding: 10px 20px;
	color: var(--text-light);

	div {
		padding-left: 5px;
	}
}
[contenteditable] {
	outline: none;
	min-width: 1px;
}
[contenteditable]:empty:before {
	content: "Add Text";
}
[contenteditable]:empty:focus:before {
	content: "";
}
</style>
