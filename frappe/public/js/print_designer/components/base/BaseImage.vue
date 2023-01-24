<template>
	<div
		:style="[postionalStyles(startX, startY, width, height)]"
		:ref="setElements(object, index)"
		:class="[MainStore.getCurrentElementsId.includes(id) && 'active-elements']"
		@mousedown.left="handleMouseDown($event, object, index)"
		@dblclick.stop="handleDblClick($event, object, index)"
		@mouseup="handleMouseUp($event, object, index)"
	>
		<img
			:style="[widthAndHeight(startX, startY, width, height), style]"
			draggable="false"
			v-if="is_dynamic ? image && Boolean(image.value) : image && Boolean(image.file_url)"
			:src="is_dynamic ? image.value : image.file_url"
			:class="['image', classes]"
			:key="id"
		/>
		<div
			class="fallback-image"
			v-else-if="
				is_dynamic ? image && !Boolean(image.value) : image && !Boolean(image.file_url)
			"
		>
			<div class="content">
				<div
					v-if="width >= 30 || height >= 30"
					draggable="false"
					v-html="frappe.utils.icon('image', 'lg')"
				></div>
				<span v-if="width >= 100 || height >= 100">{{
					is_dynamic ? "Image not Linked" : "Unable to load Image :("
				}}</span>
			</div>
		</div>
		<div class="fallback-image" v-else>
			<div class="content">
				<div
					v-if="width >= 30 || height >= 30"
					draggable="false"
					v-html="frappe.utils.icon('image', 'lg')"
				></div>
				<span v-if="width >= 100 || height >= 100"
					>Please Double click to select Image</span
				>
			</div>
		</div>
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
	</div>
</template>

<script setup>
import { useMainStore } from "../../store/MainStore";
import { useElementStore } from "../../store/ElementStore";
import { toRefs, nextTick } from "vue";
import { useElement } from "../../composables/Element";
import {
	postionalStyles,
	setCurrentElement,
	lockAxis,
	cloneElement,
	deleteCurrentElement,
} from "../../utils";
import { watch, onMounted } from "vue";
import { useDraw } from "../../composables/Draw";

const MainStore = useMainStore();
const ElementStore = useElementStore();
const props = defineProps({
	object: {
		type: Object,
		required: true,
	},
	index: {
		type: Number,
		required: true,
	},
});

const {
	id,
	type,
	DOMRef,
	isDraggable,
	isResizable,
	image,
	is_dynamic,
	startX,
	startY,
	pageX,
	pageY,
	width,
	height,
	style,
	classes,
} = toRefs(props.object);

const { setElements } = useElement({
	draggable: true,
	resizable: true,
});

const widthAndHeight = (startX, startY, width, height) => {
	let result = postionalStyles(startX, startY, width, height);
	delete result.position;
	delete result.top;
	delete result.left;
	return result;
};

const { drawEventHandler, parameters } = useDraw();

const handleMouseDown = (e, element = null, index) => {
	e.stopPropagation();
	if (MainStore.openModal) return;
	lockAxis(element, e.shiftKey);
	MainStore.isMoveStart = true;
	MainStore.moveStartElement = e.target;
	if (MainStore.activeControl == "mouse-pointer" && e.altKey) {
		element && setCurrentElement(e, element);
		cloneElement();
	} else {
		element &&
			MainStore.getCurrentElementsValues.indexOf(element) == -1 &&
			setCurrentElement(e, element);
	}
	MainStore.setActiveControl("MousePointer");
	MainStore.currentDrawListener = {
		drawEventHandler,
		parameters,
	};
};

const handleMouseUp = (e, element = null, index) => {
	if (
		e.target.classList.contains("resize-handle")
			? e.target.parentElement !== element.DOMRef
			: e.target !== element.DOMRef
	)
		return;
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
		MainStore.activeControl == "image" && (MainStore.openImageModal = element);
	}
	MainStore.setActiveControl("MousePointer");
	MainStore.moveStartElement = null;
	MainStore.isMoved = MainStore.isMoveStart = false;
	MainStore.lastCloned = null;
};

const handleDblClick = (e, element, index) => {
	element && setCurrentElement(e, element);
	MainStore.openImageModal = element;
};
</script>

<style lang="scss" scoped>
img:before {
	content: " ";
	display: block;
	position: absolute;
	height: 100%;
	width: 100%;
}
.fallback-image {
	width: 100%;
	user-select: none;
	height: 100%;
	display: flex;
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
