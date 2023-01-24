<template>
	<div
		:ref="setElements(object, index)"
		@mousedown.left="handleMouseDown($event, object, index)"
		@mouseup="handleMouseUp($event, object, index)"
		@dblclick="MainStore.openTableModal = object"
		:style="[postionalStyles(startX, startY, width, height)]"
		:class="[
			'table-container',
			classes,
			MainStore.getCurrentElementsId.includes(id) && 'active-elements',
		]"
	>
		<table id="resizeMe" class="table">
			<thead>
				<tr style="font-size: 12px" v-if="table && columns.length">
					<th
						@mousedown.stop
						@mouseup.stop
						style="width: 200px"
						v-for="column in columns"
						:key="column.fieldname"
					>
						{{ column.label }}
						<div class="resizer"></div>
					</th>
				</tr>
				<tr style="font-size: 12px; width: 100%" v-else>
					<th
						@mousedown.stop
						@mouseup.stop
						:style="{ width: `${column.width}%` }"
						v-for="column in columns"
						:key="columns.id"
					>
						<div class="resizer"></div>
					</th>
				</tr>
			</thead>
			<tbody>
				<tr
					v-if="table && columns.length"
					v-for="row in MainStore.docData[table.fieldname] || []"
					:key="row.idx"
					style="font-size: 12px"
				>
					<td
						v-for="column in columns"
						:key="column.fieldname"
						@mousedown.stop
						@mouseup.stop
					>
						{{ row[column.fieldname] }}
					</td>
				</tr>
				<tr v-else style="font-size: 12px">
					<td
						@mousedown.stop
						@mouseup.stop
						v-for="column in columns"
						:style="{ width: `${column.width}%` }"
						:key="columns.id"
					></td>
				</tr>
			</tbody>
		</table>
		<div
			class="resize-handle top-left resize-top resize-left"
			v-if="MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle top-right resize-top resize-right"
			v-if="MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle top-middle resize-top"
			v-if="MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle left-middle resize-left"
			v-if="MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle right-middle resize-right"
			v-if="MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle bottom-left resize-bottom resize-left"
			v-if="MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle bottom-middle resize-bottom"
			v-if="MainStore.getCurrentElementsId.includes(id)"
		></div>
		<div
			class="resize-handle bottom-right resize-bottom resize-right"
			v-if="MainStore.getCurrentElementsId.includes(id)"
		></div>
	</div>
</template>

<script setup>
import { useMainStore } from "../../store/MainStore";
import { useElementStore } from "../../store/ElementStore";
import { useElement } from "../../composables/Element";
import { postionalStyles, setCurrentElement, lockAxis, cloneElement } from "../../utils";
import { watch, toRefs, onMounted } from "vue";
import { useDraw } from "../../composables/Draw";

const MainStore = useMainStore();
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
	table,
	columns,
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
	drawEventHandler.mousedown(e);
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
		["rectangle", "image", "table"].includes(MainStore.activeControl)
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
	}
	MainStore.currentDrawListener.drawEventHandler.mouseup(e);
	MainStore.setActiveControl("MousePointer");
	MainStore.moveStartElement = null;
	MainStore.isMoved = MainStore.isMoveStart = false;
	MainStore.lastCloned = null;
};
</script>

<style lang="scss" scoped>
.table-container {
	background-color: var(--gray-100);
}
.table {
	border-collapse: collapse;
	overflow: hidden;
}
.table th {
	position: relative;
}
.resizer {
	/* Displayed at the right side of column */
	position: absolute;
	top: 0;
	right: 0;
	width: 5px;
	height: 100%;
	cursor: col-resize;
	user-select: none;
	border-right: 1px solid var(--gray-200);
}
.table th,
.table td {
	border: 1px solid black;
}
.table tr:last-child {
	border: 1px solid black;
}

.resizer:hover,
.resizing {
	border-right: 2px solid var(--primary-color);
}

[contenteditable] {
	outline: none;
}
[contenteditable]:empty:before {
	content: attr(data-placeholder);
}
[contenteditable]:empty:focus:before {
	content: "";
}
.text-hover:hover {
	box-sizing: border-box !important;
	border-bottom: 1px solid var(--primary-color) !important;
}
</style>
