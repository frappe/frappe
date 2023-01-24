<template>
	<div
		:style="[style, postionalStyles(startX, startY, width, height)]"
		:class="[
			'rectangle',
			{ 'active-elements': MainStore.getCurrentElementsId.includes(id) },
			classes,
		]"
		:ref="setElements(object, index)"
		@mousedown.left.stop="handleMouseDown($event, object, index)"
		@mouseup.left="handleMouseUp($event, object, index)"
	>
		<div
			class="resize-handle top-left resize-top resize-left"
			v-if="
				MainStore.activeControl == 'mouse-pointer' &&
				MainStore.getCurrentElementsId.includes(id)
			"
		></div>
		<div
			class="resize-handle top-right resize-top resize-right"
			v-if="
				MainStore.activeControl == 'mouse-pointer' &&
				MainStore.getCurrentElementsId.includes(id)
			"
		></div>
		<div
			class="resize-handle top-middle resize-top"
			v-if="
				MainStore.activeControl == 'mouse-pointer' &&
				MainStore.getCurrentElementsId.includes(id)
			"
		></div>
		<div
			class="resize-handle left-middle resize-left"
			v-if="
				MainStore.activeControl == 'mouse-pointer' &&
				MainStore.getCurrentElementsId.includes(id)
			"
		></div>
		<div
			class="resize-handle right-middle resize-right"
			v-if="
				MainStore.activeControl == 'mouse-pointer' &&
				MainStore.getCurrentElementsId.includes(id)
			"
		></div>
		<div
			class="resize-handle bottom-left resize-bottom resize-left"
			v-if="
				MainStore.activeControl == 'mouse-pointer' &&
				MainStore.getCurrentElementsId.includes(id)
			"
		></div>
		<div
			class="resize-handle bottom-middle resize-bottom"
			v-if="
				MainStore.activeControl == 'mouse-pointer' &&
				MainStore.getCurrentElementsId.includes(id)
			"
		></div>
		<div
			class="resize-handle bottom-right resize-bottom resize-right"
			v-if="
				MainStore.activeControl == 'mouse-pointer' &&
				MainStore.getCurrentElementsId.includes(id)
			"
		></div>
		<template v-for="(object, index) in object.childrens" :key="object.id">
			<BaseRectangle v-if="object.type == 'rectangle'" v-bind="{ object, index }" />
			<BaseStaticText
				v-else-if="object.type == 'text' && !object.is_dynamic"
				v-bind="{ object, index }"
			/>
			<BaseDynamicText
				v-else-if="object.type == 'text' && object.is_dynamic"
				v-bind="{ object, index }"
			/>
			<BaseTable v-else-if="object.type == 'table'" v-bind="{ object, index }" />
			<BaseImage v-else-if="object.type == 'image'" v-bind="{ object, index }" />
		</template>
	</div>
</template>

<script setup>
import { toRefs } from "vue";
import { useDraw } from "../../composables/Draw";
import { useChangeValueUnit } from "../../composables/ChangeValueUnit";
import { useElement } from "../../composables/Element";
import { useMainStore } from "../../store/MainStore";
import { useElementStore } from "../../store/ElementStore";
import { setCurrentElement, cloneElement, deleteCurrentElement, lockAxis } from "../../utils";
import BaseStaticText from "./BaseStaticText.vue";
import BaseDynamicText from "./BaseDynamicText.vue";
import BaseImage from "./BaseImage.vue";
import BaseTable from "./BaseTable.vue";

const props = defineProps(["object", "index"]);
const {
	id,
	type,
	startX,
	startY,
	parent,
	pageX,
	pageY,
	width,
	height,
	style,
	classes,
	childrens,
	DOMRef,
	isDraggable,
	isResizable,
} = toRefs(props.object);
const ElementStore = useElementStore();
const MainStore = useMainStore();

const postionalStyles = (startX, startY, width, height) => {
	const convertUnit = (input) => {
		let convertedUnit = useChangeValueUnit({
			inputString: input,
			defaultInputUnit: "px",
			convertionUnit: MainStore.page.UOM,
		});
		return `${convertedUnit.value.toFixed(3)}${convertedUnit.unit}`;
	};
	return {
		position: "absolute",
		top: convertUnit(startY),
		left: convertUnit(startX),
		width: convertUnit(width),
		height: convertUnit(height),
	};
};

const { setElements } = useElement({
	draggable: true,
	resizable: true,
});

const { drawEventHandler, parameters } = useDraw();

const handleMouseDown = (e, element = null, index) => {
	if (MainStore.openModal) return;
	lockAxis(element, e.shiftKey);
	MainStore.isMoveStart = true;
	MainStore.moveStartElement = e.target;
	if (MainStore.activeControl == "mouse-pointer" && e.altKey) {
		element && setCurrentElement(e, element);
		cloneElement();
		drawEventHandler.mousedown(e);
	} else {
		if (["rectangle", "image"].includes(MainStore.activeControl)) {
			const newElement = ElementStore.createNewObject(
				{
					startX: e.offsetX,
					startY: e.offsetY,
					pageX: e.x,
					pageY: e.y,
				},
				element
			);
			drawEventHandler.mousedown({
				startX: e.offsetX,
				startY: e.offsetY,
				clientX: e.clientX,
				clientY: e.clientY,
			});
			newElement && setCurrentElement(e, newElement);
		} else if (MainStore.activeControl == "text") {
			if (MainStore.getCurrentElementsId.length) {
				MainStore.currentElements = {};
			} else {
				const newElement = ElementStore.createNewObject(
					{
						startX: e.offsetX,
						startY: e.offsetY,
						pageX: e.x,
						pageY: e.y,
					},
					element
				);
				newElement && setCurrentElement(e, newElement);
				if (MainStore.textControlType == "dynamic") {
					MainStore.openDyanmicModal = newElement;
				}
			}
		} else {
			element && setCurrentElement(e, element);
		}
	}
	MainStore.currentDrawListener = {
		drawEventHandler,
		parameters,
		restrict: {
			top: startY.value - e.target.offsetTop - 1,
			bottom: startY.value + height.value - e.target.offsetTop - 1,
			left: startX.value - e.target.offsetLeft - 1,
			right: startX.value + width.value - e.target.offsetLeft - 1,
		},
	};
};

const handleMouseUp = (e, element = null, index) => {
	if (
		e.target.classList.contains("resize-handle")
			? e.target.parentElement !== element.DOMRef
			: e.target !== element.DOMRef
	)
		return;
	if (MainStore.isDropped) {
		MainStore.currentElements = MainStore.isDropped;
		MainStore.isDropped = null;
		return;
	}
	if (
		!MainStore.openModal &&
		!MainStore.isMoved &&
		MainStore.activeControl == "mouse-pointer" &&
		e.target == element.DOMRef
	) {
		element && setCurrentElement(e, element);
	}
	if (
		MainStore.lastCreatedElement &&
		!MainStore.openModal &&
		!MainStore.isMoved &&
		["rectangle", "image"].includes(MainStore.activeControl)
	) {
		if (!MainStore.modalLocation.isDragged) {
			clientX = e.clientX;
			clientY = e.clientY;
			if (clientX - 250 > 0) clientX = clientX - 250;
			if (clientY - 180 > 0) clientY = clientY - 180;
			MainStore.modalLocation.x = clientX;
			MainStore.modalLocation.y = clientY;
		}
		MainStore.currentElements = {};
		MainStore.currentElements[MainStore.lastCreatedElement.id] = MainStore.lastCreatedElement;
		MainStore.openModal = true;
	} else if (
		MainStore.lastCloned &&
		!MainStore.isMoved &&
		MainStore.activeControl == "mouse-pointer"
	) {
		deleteCurrentElement();
	} else {
		MainStore.currentDrawListener.drawEventHandler.mouseup(e);
	}
	MainStore.moveStartElement = null;
	MainStore.isMoved = MainStore.isMoveStart = false;
	MainStore.lastCloned = null;
};
</script>

<style lang="scss" scoped></style>
