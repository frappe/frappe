<template>
	<AppModal
		:openModal="!!openTableModal"
		v-bind="{ size }"
		:backdrop="true"
		:isDraggable="false"
		@cancelClick="cancelClick"
		@primaryClick="primaryClick"
	>
		<template #title>Table</template>
		<template #body>
			<div>
				<div class="dynamic-results col-sm-12 result-section row">
					<div
						class="result-body col-sm-4"
						v-for="field in MainStore.getTableMetaFields"
						:key="field.fieldname"
						:value="field.fieldname"
					>
						<div
							class="result"
							@click="handleTableClick(field)"
							:class="{
								'result-selected': field.fieldname == selectedTable?.fieldname,
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
				<div
					v-if="openTableModal.table"
					class="table-results col-sm-12 result-section row"
				>
					<div
						class="result-body col-sm-4"
						v-for="field in MainStore.metaFields.find(
							(el) => el.fieldname == selectedTable?.fieldname
						)?.childfields"
						:key="field.fieldname"
						:value="field.fieldname"
					>
						<div
							class="result column-field"
							@click="handleColumnClick(field)"
							:class="{
								'column-selected': selectedColumns.indexOf(field) != -1,
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
				<div class="table-container"></div>
			</div>
		</template>
	</AppModal>
</template>
<script setup>
import { ref, onMounted, watch, nextTick } from "vue";
import { useMainStore } from "../../store/MainStore";
import AppModal from "./AppModal.vue";
const MainStore = useMainStore();
const props = defineProps(["openTableModal", "updateDynamicTextModal"]);
const parentField = ref("");
const fieldnames = ref([]);
const selectedTable = ref(null);
const selectedColumns = ref([]);

watch(selectedTable, () => {
	if (selectedTable.value) {
		let table = MainStore.metaFields.find(
			(el) => el.fieldname == selectedTable.value.fieldname
		);
		if (!table) return;
		props.openTableModal.table = table;
	}
});

onMounted(() => {
	if (props.openTableModal.table) {
		selectedTable.value = props.openTableModal.table;
		selectedColumns.value = props.openTableModal.columns;
	}
});

const size = {
	width: "75vw",
	height: "82vh",
	left: "6vw",
	top: "3vh",
};

const handleTableClick = async (table) => {
	selectedTable.value = table;
	selectedColumns.value = [];
};
const handleColumnClick = async (field) => {
	let index = selectedColumns.value.indexOf(field);
	if (index == -1) {
		selectedColumns.value.push(field);
	} else {
		selectedColumns.value.splice(index, 1);
	}
};

const primaryClick = (e) => {
	MainStore.openTableModal.table = selectedTable.value;
	MainStore.openTableModal.columns = selectedColumns.value;
	MainStore.openTableModal = null;
};
const cancelClick = () => {
	MainStore.openTableModal = null;
};
</script>
<style scoped lang="scss">
.result-text {
	display: flex;
	align-items: center;
	justify-content: space-between;
}
.table-container {
	border: 1px solid red;
	height: 25vh;
	width: 100%;
	margin-top: 4vh;
}
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
.result:hover,
.result-selected {
	border: 1px solid var(--success);
	padding: 7px 0;
	border-radius: var(--border-radius);

	.icon-show {
		display: unset;
		color: var(--success);
	}
}
.column-field:hover,
.column-selected {
	border: 1px solid var(--primary);
	padding: 7px 0;
	border-radius: var(--border-radius);
}
.column-selected .icon-show {
	display: unset;
	color: var(--primary);
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
.dynamic-results::-webkit-scrollbar,
.dynamic-sidebar::-webkit-scrollbar {
	width: 5px;
	height: 5px;
}
.dynamic-results::-webkit-scrollbar-thumb,
.dynamic-sidebar::-webkit-scrollbar-thumb {
	background: "var(--gray-200)";
	border-radius: 6px;
}
.dynamic-results::-webkit-scrollbar-track,
.dynamic-results::-webkit-scrollbar-corner {
	background: white;
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
	max-height: calc(8vh);
	overflow: auto;
}
.modal-dialog .table-results {
	height: calc(40vh);
	overflow: auto;
}
</style>
