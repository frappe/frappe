<template>
	<AppModal
		:openModal="openModal"
		v-bind="{ size }"
		:backdrop="false"
		:isDraggable="true"
		@cancelClick="cancelClick"
		@primaryClick="primaryClick"
	>
		<template #title>Rectangle</template>
		<template #body>
			<div class="d-flex">
				<div class="mx-2">
					<label class="mx-1" for="modalWidthInput">Width:</label>
					<div class="input-group">
						<input
							autocomplete="off"
							:value="`${useChangeValueUnit({
								inputString: width,
								convertionUnit: MainStore.page.UOM,
							}).value.toFixed(2)} ${MainStore.page.UOM}`"
							@keyup.stop
							@change.stop="
								(e) => {
									width = useChangeValueUnit({
										inputString: e.target.value,
										defaultInputUnit: MainStore.page.UOM,
									}).value;
								}
							"
							@keyup.enter="primaryClick"
							v-focus.select
							class="form-control mx-1"
							id="modalWidthInput"
							style="min-width: 50px"
						/>
					</div>
				</div>
				<div class="mx-2">
					<label class="mx-1" for="modalHeightInput">Height:</label>
					<div class="input-group">
						<input
							autocomplete="off"
							:value="`${useChangeValueUnit({
								inputString: height,
								convertionUnit: MainStore.page.UOM,
							}).value.toFixed(2)} ${MainStore.page.UOM}`"
							@keyup.stop
							@change.stop="
								(e) => {
									height = useChangeValueUnit({
										inputString: e.target.value,
										defaultInputUnit: MainStore.page.UOM,
									}).value;
								}
							"
							@keyup.enter="primaryClick"
							class="form-control mx-1"
							id="modalHeightInput"
							style="min-width: 50px"
						/>
					</div>
				</div>
			</div>
		</template>
	</AppModal>
</template>
<script setup>
import { ref, onMounted, watchEffect } from "vue";
import { useChangeValueUnit } from "../../composables/ChangeValueUnit";
import { useMainStore } from "../../store/MainStore";
import { useElementStore } from "../../store/ElementStore";
import { deleteCurrentElement } from "../../utils";
import AppModal from "./AppModal.vue";
const MainStore = useMainStore();
const ElementStore = useElementStore();
const props = defineProps(["openModal", "updateOpenModal"]);
const prevHeight = ref(0);
const prevWidth = ref(0);
const size = {
	width: "230px",
	height: "80px",
	left: "calc(var(--modal-x) + 1px)",
	top: "calc(var(--modal-y) + 1px)",
};
const height = ref(0);
const width = ref(0);
const primaryClick = (e) => {
	if (height.value < 1 || width.value < 1) {
		deleteCurrentElement();
	}
	MainStore.getCurrentElementsValues.forEach((element) => {
		element && (element.height = height.value);
		element && (element.width = width.value);
	});
	width.value = 0;
	height.value = 0;
	props.updateOpenModal(false);
};
const cancelClick = () => {
	props.updateOpenModal(!props.openModal, true);
	MainStore.getCurrentElementsValues.forEach((element) => {
		element && (element.height = prevHeight.value);
		element && (element.width = prevWidth.value);
	});
	width.value = 0;
	height.value = 0;
	props.updateOpenModal(false);
	if (height.value < 1 || width.value < 1) {
		deleteCurrentElement();
	}
};

onMounted(() => {
	MainStore.getCurrentElementsValues.forEach((element) => {
		element && (prevHeight.value = element.height);
		element && (prevWidth.value = element.width);
	});
});
watchEffect(() => {
	if (props.openModal && (height.value || width.value)) {
		let element = MainStore.lastCreatedElement;
		element && (element.height = height.value);
		element && (element.width = width.value);
	}
});

const vFocus = {
	mounted: (el, binding) => {
		el.focus();
		binding.modifiers.select && el.select();
	},
};
</script>
<style scoped>
label,
input {
	position: relative;
	display: block;
	box-sizing: border-box;
}

/* label::after {
	content: attr(data-append);
	position: absolute;
	top: 9px;
	left: 70px;
	font-family: Inter;
	font-size: 10px;
	display: block;
	color: var(--gray-600);
} */

.form-control:focus {
	box-shadow: none;
	border: 1px solid var(--primary);
}
</style>
