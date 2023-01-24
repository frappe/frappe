<template>
	<div
		@dblclick.stop="handleDblClick($event, object, index)"
		@mousedown.left="handleMouseDown($event, object, index)"
		@mouseup="handleMouseUp($event, object, index)"
		:style="[
			postionalStyles(startX, startY, width, height),
			!isFixedSize && 'width:fit-content; height:fit-content;',
		]"
		:class="MainStore.getCurrentElementsId.includes(id) ? 'active-elements' : 'text-hover'"
		:ref="setElements(object, index)"
		:key="id"
	>
		<p
			:contenteditable="contenteditable"
			@keydown.stop="handleKeyDown"
			@focus="handleFocus"
			@blur="handleBlur"
			@keyup.stop
			:style="[
				style,
				'overflow:hidden;',
				widthAndHeight(startX, startY, width, height),
				!isFixedSize && 'width:fit-content; height:fit-content;',
			]"
			:class="['staticText', classes]"
			v-if="type == 'text'"
			data-placeholder=""
			v-html="content"
		></p>
		<div
			class="resize-handle top-left resize-top resize-left"
			v-if="!contenteditable && MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle top-right resize-top resize-right"
			v-if="!contenteditable && MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle top-middle resize-top"
			v-if="!contenteditable && MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle left-middle resize-left"
			v-if="!contenteditable && MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle right-middle resize-right"
			v-if="!contenteditable && MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle bottom-left resize-bottom resize-left"
			v-if="!contenteditable && MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle bottom-middle resize-bottom"
			v-if="!contenteditable && MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle bottom-right resize-bottom resize-right"
			v-if="!contenteditable && MainStore.getCurrentElementsId.includes(id)"
		></div>
	</div>
</template>

<script setup>
import { useMainStore } from "../../store/MainStore";
import { useElementStore } from "../../store/ElementStore";
import { toRefs } from "vue";
import { useElement } from "../../composables/Element";
import { postionalStyles, setCurrentElement, lockAxis, cloneElement } from "../../utils";
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

const widthAndHeight = (startX, startY, width, height) => {
	let result = postionalStyles(startX, startY, width, height);
	delete result.position;
	delete result.top;
	delete result.left;
	return result;
};

const {
	id,
	type,
	DOMRef,
	content,
	contenteditable,
	isFixedSize,
	is_dynamic,
	dynamicContent,
	isDraggable,
	isResizable,
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

const { drawEventHandler, parameters } = useDraw();

const toggleDragResize = (toggle) => {
	isDraggable.value = toggle;
	isResizable.value = toggle;
	props.object.contenteditable = !toggle;
};
watch(
	() => MainStore.activeControl,
	() => {
		if (MainStore.activeControl == "text") {
			toggleDragResize(false);
		} else {
			toggleDragResize(true);
		}
	}
);

const handleMouseDown = (e, element, index) => {
	lockAxis(element, e.shiftKey);
	if (MainStore.openModal) return;
	MainStore.currentDrawListener = { drawEventHandler, parameters };
	element && setCurrentElement(e, element);
	if (MainStore.activeControl == "mouse-pointer" && e.altKey) {
		element && setCurrentElement(e, element);
		cloneElement();
		drawEventHandler.mousedown(e);
	}
	e.stopPropagation();
	if (MainStore.activeControl != "rectangle") {
	}
};

const handleMouseUp = (e, element = null, index) => {
	if (MainStore.activeControl == "mouse-pointer") {
		MainStore.currentDrawListener.drawEventHandler.mouseup(e);
		MainStore.moveStartElement = null;
		MainStore.isMoved = MainStore.isMoveStart = false;
		MainStore.lastCloned = null;
		if (MainStore.isDropped) {
			MainStore.currentElements = MainStore.isDropped;
			MainStore.isDropped = null;
			return;
		}
	}
};

const handleDblClick = (e, element, index) => {
	element && setCurrentElement(e, element);
	contenteditable.value = true;
	isDraggable.value = false;
	isResizable.value = false;
	MainStore.setActiveControl("Text");
	setTimeout(function () {
		DOMRef.value.firstElementChild.focus();
	}, 0);
};

onMounted(() =>
	setTimeout(function () {
		DOMRef.value.firstElementChild.focus();
		DOMRef.value.firstElementChild.dataset.placeholder = "Type Something...";
	}, 0)
);

const handleBlur = (e) => {
	let targetRect = e.target.getBoundingClientRect();
	if (!isFixedSize.value) {
		width.value = targetRect.width + 2;
		height.value = targetRect.height + 2;
	}
	content.value = DOMRef.value.firstElementChild.innerHTML;
	MainStore.getCurrentElementsId.includes(id.value) &&
		DOMRef.value.classList.add("active-elements");
};

const handleKeyDown = (e) => {
	if (e.code == "Tab") {
		handleBlur(e);
		DOMRef.value.firstElementChild.blur();
		e.preventDefault();
	}
};

const handleFocus = (e) => {
	DOMRef.value.classList.remove("active-elements");
};
</script>

<style scoped>
[contenteditable] {
	outline: none;
	min-width: 1px;
}
[contenteditable]:empty:before {
	content: attr(data-placeholder);
}
[contenteditable]:empty:focus:before {
	content: "";
}
/* .text-hover:hover {
	box-sizing: border-box !important;
	border-bottom: 1px solid var(--primary-color) !important;
} */
</style>
