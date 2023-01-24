<template>
	<div>
		<div class="canvas" id="canvas" v-marquee="marqueeOptions">
			<div
				class="main-container"
				:ref="
					(el) => {
						MainStore.mainContainer = el;
					}
				"
				:style="[MainStore.getPageSettings, { cursor: MainStore.cursor }]"
				@mousedown.left="handleMouseDown"
				@mousemove="handleMouseMove"
				@mouseleave="handleMouseLeave"
				@mouseup.left="handleMouseUp"
			>
				<template v-for="(object, index) in ElementStore.Elements" :key="object.id">
					<component
						:is="
							object.type == 'text'
								? isComponent[object.type][
										object.is_dynamic ? 'dynamic' : 'static'
								  ]
								: isComponent[object.type]
						"
						v-bind="{ object, index }"
					></component>
				</template>
			</div>
			<AppWidthHeightModal
				v-if="MainStore.openModal"
				:openModal="MainStore.openModal"
				:updateOpenModal="updateOpenModal"
			/>
			<AppDynamicTextModal
				v-if="MainStore.openDyanmicModal"
				:openDyanmicModal="MainStore.openDyanmicModal"
				:updateDynamicTextModal="updateOpenModal"
			/>
			<AppTableModal
				v-if="MainStore.openTableModal"
				:openTableModal="MainStore.openTableModal"
				:updateDynamicTextModal="updateOpenModal"
			/>
			<AppImageModal
				v-if="MainStore.openImageModal"
				:openImageModal="MainStore.openImageModal"
				:updateDynamicTextModal="updateOpenModal"
			/>
		</div>
	</div>
</template>
<script setup>
import { watchEffect, onMounted, nextTick } from "vue";
import { useMainStore } from "../../store/MainStore";
import { useElementStore } from "../../store/ElementStore";
import { useMarqueeSelection } from "../../composables/MarqueeSelectionTool";
import AppWidthHeightModal from "./AppWidthHeightModal.vue";
import AppDynamicTextModal from "./AppDynamicTextModal.vue";
import { useDraw } from "../../composables/Draw";
import BaseRectangle from "../base/BaseRectangle.vue";
import BaseImage from "../base/BaseImage.vue";
import BaseStaticText from "../base/BaseStaticText.vue";
import BaseDynamicText from "../base/BaseDynamicText.vue";
import { updateElementParameters, setCurrentElement, recursiveChildrens } from "../../utils";
import { useChangeValueUnit } from "../../composables/ChangeValueUnit";
import AppImageModal from "./AppImageModal.vue";
import BaseTable from "../base/BaseTable.vue";
import AppTableModal from "./AppTableModal.vue";
// import BaseBarcode from "../base/BaseBarcode.vue";
// import BaseCompontent from "../base/BaseCompontent.vue";
const isComponent = Object.freeze({
	rectangle: BaseRectangle,
	text: {
		static: BaseStaticText,
		dynamic: BaseDynamicText,
	},
	image: BaseImage,
	table: BaseTable,
	// barcode: BaseBarcode,
	// component: BaseCompontent,
});

const MainStore = useMainStore();
const ElementStore = useElementStore();
const { vMarquee } = useMarqueeSelection();
const marqueeOptions = {
	beforeDraw: "isMarqueeActive",
};

const { drawEventHandler, parameters } = useDraw();

const handleMouseDown = (e) => {
	if (MainStore.openModal) return;
	if (
		(MainStore.isDrawing && !MainStore.isMarqueeActive) ||
		e.target != MainStore.mainContainer
	) {
		e.stopPropagation();
	}
	if (e.target == MainStore.mainContainer) {
		MainStore.isMoveStart = true;
		MainStore.moveStartElement = e.target;
		const convertToPx = (value) =>
			useChangeValueUnit({
				inputString: value,
				defaultInputUnit: MainStore.page.UOM,
			}).value;
		let top = 0;
		let bottom =
			convertToPx(MainStore.page.height) -
			convertToPx(MainStore.page.marginTop) -
			convertToPx(MainStore.page.marginBottom);
		let left = 0;
		let right =
			convertToPx(MainStore.page.width) -
			convertToPx(MainStore.page.marginLeft) -
			convertToPx(MainStore.page.marginRight);
		if (["rectangle", "image", "table"].includes(MainStore.activeControl)) {
			MainStore.currentDrawListener = {
				drawEventHandler,
				parameters,
				restrict: {
					top,
					bottom,
					left,
					right,
				},
			};
			const newElement = ElementStore.createNewObject(e);
			newElement && setCurrentElement(e, newElement);
			drawEventHandler.mousedown({
				startX: e.offsetX,
				startY: e.offsetY,
				clientX: e.clientX,
				clientY: e.clientY,
			});
		} else if (MainStore.activeControl == "text") {
			if (MainStore.getCurrentElementsId.length) {
				MainStore.currentElements = {};
			} else {
				const newElement = ElementStore.createNewObject(e);
				newElement && setCurrentElement(e, newElement);
				if (MainStore.textControlType == "dynamic") {
					MainStore.openDyanmicModal = newElement;
				}
			}
		} else {
			MainStore.currentDrawListener = { drawEventHandler, parameters };
		}
	}
};

const handleMouseMove = (e) => {
	if (MainStore.openModal || !MainStore.isMoveStart) return;
	if (
		(MainStore.isDrawing && !MainStore.isMarqueeActive) ||
		(e.target != MainStore.mainContainer && !MainStore.isMarqueeActive)
	) {
		e.stopPropagation();
	}
	if (MainStore.activeControl == "text") return;
	if (MainStore.currentDrawListener === null)
		MainStore.currentDrawListener = { drawEventHandler, parameters };
	MainStore.currentDrawListener.drawEventHandler.mousemove(e);
	if (
		!MainStore.isMoved &&
		(MainStore.currentDrawListener.parameters.width > 3 ||
			MainStore.currentDrawListener.parameters.height > 3)
	) {
		MainStore.isMoved = true;
	}
	if (
		!MainStore.openModal &&
		["rectangle", "image", "table"].includes(MainStore.activeControl) &&
		MainStore.lastCreatedElement &&
		MainStore.currentDrawListener.parameters.isMouseDown
	) {
		updateElementParameters(e);
		if (MainStore.activeControl == "table") {
			let width = MainStore.currentDrawListener.parameters.width;
			let columns = Math.floor(width / 100);
			let elementColumns = MainStore.lastCreatedElement.columns;
			!elementColumns.length && elementColumns.push({ id: 0, width: 100 });
			if (width > 100) {
				let columnDif = columns - elementColumns.length;
				if (columnDif == 0) {
					return;
				} else if (columnDif < 0) {
					elementColumns.pop();
					elementColumns.forEach((element) => {
						element.width = 100 / (elementColumns.length || 1);
					});
				} else {
					for (let index = 0; index < columnDif; index++) {
						elementColumns.push({
							id: elementColumns.length,
						});
					}
					elementColumns.forEach((element) => {
						element.width = 100 / (elementColumns.length || 1);
					});
				}
			}
		}
	}
};

const handleMouseUp = (e) => {
	if (MainStore.isDropped) {
		MainStore.currentElements = MainStore.isDropped;
		MainStore.isDropped = null;
		return;
	}
	if (MainStore.isDrawing && !MainStore.isMarqueeActive) {
		e.stopPropagation();
	}
	if (e.target == MainStore.mainContainer) {
		if (["rectangle", "image", "table"].includes(MainStore.activeControl)) {
			if (
				MainStore.lastCreatedElement &&
				!MainStore.openModal &&
				!MainStore.isMoved &&
				MainStore.currentDrawListener.drawEventHandler.parameters.isMouseDown
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
				MainStore.currentElements[MainStore.lastCreatedElement.id] =
					MainStore.lastCreatedElement;
				MainStore.openModal = true;
			}
		} else if (MainStore.activeControl == "text") {
		} else {
			MainStore.currentDrawListener.drawEventHandler.mouseup(e);
		}
		MainStore.isMoveStart = false;
		MainStore.moveStartElement = null;
		MainStore.isMoved = false;
	}
	if (MainStore.isDrawing && MainStore.lastCreatedElement?.type == "image") {
		!MainStore.openImageModal &&
			nextTick(() => (MainStore.openImageModal = MainStore.lastCreatedElement));
		MainStore.setActiveControl("MousePointer");
	}
	if (MainStore.isDrawing && MainStore.lastCreatedElement?.type == "rectangle") {
		const recursiveParentLoop = (currentElement, offset = { startX: 0, startY: 0 }) => {
			if (currentElement.parent != ElementStore.Elements) {
				let currentDOM = MainStore.lastCreatedElement.DOMRef.getBoundingClientRect();
				let parentDOM = currentElement.parent.DOMRef.getBoundingClientRect();
				if (
					parentDOM.left > currentDOM.left + 1 ||
					parentDOM.top > currentDOM.top + 1 ||
					parentDOM.bottom < currentDOM.bottom - 1 ||
					parentDOM.right < currentDOM.right - 1
				) {
					offset.startX += currentElement.parent.startX + 1;
					offset.startY += currentElement.parent.startY + 1;
					recursiveParentLoop(currentElement.parent, offset);
				} else {
					if (MainStore.lastCreatedElement === currentElement) return;
					let tempElement = { ...MainStore.lastCreatedElement.parent.childrens.pop() };
					tempElement.id = frappe.utils.get_random(10);
					tempElement.index = null;
					tempElement.DOMRef = null;
					tempElement.parent = currentElement.parent;
					tempElement.startX += offset.startX;
					tempElement.startY += offset.startY;
					tempElement.style = { ...tempElement.style };
					currentElement.parent.childrens.push(tempElement);
					MainStore.currentElements = {};
					MainStore.currentElements[tempElement.id] = tempElement;
					return;
				}
			} else if (MainStore.lastCreatedElement.parent != ElementStore.Elements) {
				let tempElement = { ...MainStore.lastCreatedElement.parent.childrens.pop() };
				tempElement.id = frappe.utils.get_random(10);
				tempElement.index = null;
				tempElement.DOMRef = null;
				tempElement.parent = ElementStore.Elements;
				tempElement.startX += offset.startX;
				tempElement.startY += offset.startY;
				tempElement.style = { ...tempElement.style };
				ElementStore.Elements.push(tempElement);
				MainStore.currentElements = {};
				MainStore.currentElements[tempElement.id] = tempElement;
				return;
			}
		};
		recursiveParentLoop(MainStore.lastCreatedElement);
		let Rect = {
			top: MainStore.lastCreatedElement.startY,
			left: MainStore.lastCreatedElement.startX,
			bottom: MainStore.lastCreatedElement.startY + MainStore.lastCreatedElement.height,
			right: MainStore.lastCreatedElement.startX + MainStore.lastCreatedElement.width,
		};
		let parentElement;
		if (MainStore.lastCreatedElement.parent == ElementStore.Elements) {
			parentElement = MainStore.lastCreatedElement.parent;
		} else {
			parentElement = MainStore.lastCreatedElement.parent.childrens;
		}
		parentElement.forEach((element) => {
			nextTick(() => {
				if (element.id != MainStore.lastCreatedElement.id) {
					let elementRect = {
						top: element.startY,
						left: element.startX,
						bottom: element.startY + element.height,
						right: element.startX + element.width,
					};
					if (
						Rect.top < elementRect.top &&
						Rect.left < elementRect.left &&
						Rect.right > elementRect.right &&
						Rect.bottom > elementRect.bottom
					) {
						let splicedElement;
						if (element.parent == ElementStore.Elements) {
							splicedElement = {
								...element.parent.splice(
									element.parent.find((el) => el == element),
									1
								)[0],
							};
						} else {
							splicedElement = {
								...element.parent.childrens.splice(
									element.parent.childrens.find((el) => el == element),
									1
								)[0],
							};
						}
						splicedElement.startX =
							element.startX - MainStore.lastCreatedElement.startX;
						splicedElement.startY =
							element.startY - MainStore.lastCreatedElement.startY;
						splicedElement.parent = MainStore.lastCreatedElement;
						recursiveChildrens({ element: splicedElement, isClone: false });
						if (splicedElement.parent === ElementStore.Elements) {
							splicedElement.parent.push(splicedElement);
						} else {
							splicedElement.parent.childrens.push(splicedElement);
						}
					}
				}
			});
		});
		MainStore.currentDrawListener.drawEventHandler.mouseup(e);
	}
};

const handleMouseLeave = (e) => {
	if (!e.buttons) return;
	MainStore.setActiveControl("MousePointer");
	if (MainStore.currentDrawListener) {
		MainStore.currentDrawListener.drawEventHandler.mouseup(e);
	}
	MainStore.isMoveStart = false;
	MainStore.moveStartElement = null;
	MainStore.isMoved = false;
	MainStore.lastCloned = null;
};
const updateOpenModal = (value, isCancelled = false) => {
	MainStore.openModal = value;
	if (isCancelled && MainStore.getCurrentElementsId.length) {
		MainStore.getCurrentElementsId.forEach((id) => {
			delete ElementStore.Elements[id];
		});
	}
	MainStore.setActiveControl("MousePointer");
};

onMounted(() => {
	watchEffect(() => {
		if (MainStore.screenStyleSheet) {
			for (let i = MainStore.screenStyleSheet.cssRules.length - 1; i >= 0; i--) {}
			if (MainStore.globalStyles) {
				MainStore.addGlobalRules();
			}
		}
	});
	watchEffect(() => {
		if (MainStore.screenStyleSheet || MainStore.printCssVariables) {
			if (MainStore.printCssVariableID != null) {
				MainStore.screenStyleSheet.deleteRule(MainStore.printCssVariableID);
			}
			MainStore.printCssVariableID = MainStore.addStylesheetRules([
				[
					":root, ::after, ::before",
					["--print-width", MainStore.page.width + MainStore.page.UOM],
					["--print-height", MainStore.page.height + MainStore.page.UOM],
					[
						"--print-container-width",
						MainStore.page.width + MainStore.page.marginLeft + MainStore.page.UOM,
					],
					[
						"--print-container-height",
						MainStore.page.height + MainStore.page.marginTop + MainStore.page.UOM,
					],
					["--print-margin-top", -MainStore.page.marginTop + MainStore.page.UOM],
					["--print-margin-bottom", MainStore.page.marginBottom + MainStore.page.UOM],
					["--print-margin-left", -MainStore.page.marginLeft + MainStore.page.UOM],
					["--print-margin-right", MainStore.page.marginRight + MainStore.page.UOM],
				],
			]);
			MainStore.printCssVariables =
				MainStore.screenStyleSheet.cssRules[MainStore.printCssVariableID];
		}
	});
});
watchEffect(() => {
	if (MainStore.screenStyleSheet && MainStore.page) {
		MainStore.addStylesheetRules([
			[
				"@page",
				["size", MainStore.page.width + "mm " + MainStore.page.height + "mm"],
				["margin-top", MainStore.page.marginTop + "mm"],
				["margin-bottom", MainStore.page.marginBottom + "mm"],
				["margin-left", MainStore.page.marginLeft + "mm"],
				["margin-right", MainStore.page.marginRight + "mm"],
			],
		]);
	}
});
watchEffect(() => {
	if (MainStore.screenStyleSheet && MainStore.modalLocation) {
		MainStore.addStylesheetRules([
			[
				":root",
				["--modal-x", MainStore.modalLocation.x + "px"],
				["--modal-y", MainStore.modalLocation.y + "px"],
			],
		]);
	}
});
</script>
<style lang="scss">
.rectangle:has(.active-elements) {
	z-index: 9999;
}
.active-elements {
	z-index: 9999 !important;
	border: 1px solid var(--primary) !important;
	padding: 0px !important;
}
.selection {
	border: 1px solid var(--primary);
	background-color: rgba(36, 144, 239, 0.2);
	position: absolute;
}
.canvas {
	display: block;
	z-index: 0;
	position: relative;
	flex: 1;
}
.main-container {
	position: relative;
	background-color: white;
	margin: 50px auto;
	margin-top: calc((-1 * var(--print-margin-top)) + 50px);
	height: 100%;
}
.main-container:after {
	display: block;
	position: absolute;
	content: "";
	background: var(--gray-300);
	height: var(--print-height);
	width: var(--print-width);
	z-index: -1;
	margin-top: calc(var(--print-margin-top));
	margin-left: calc(var(--print-margin-left));
	margin-right: calc(var(--print-margin-right) * -1);
	margin-bottom: calc(var(--print-margin-bottom) * -1);
}
.resize-handle {
	width: 6px;
	height: 6px;
	background: white;
	border: 1px solid var(--primary-color);
	position: absolute;
	z-index: 9999;
}
.top-left {
	left: -4px;
	top: -4px;
	cursor: nwse-resize;
}
.top-middle {
	top: -4px;
	left: calc(50% - 3px);
	cursor: ns-resize;
}
.top-right {
	right: -4px;
	top: -4px;
	cursor: nesw-resize;
}
.right-middle {
	right: -4px;
	top: calc(50% - 3px);
	cursor: ew-resize;
}
.left-middle {
	left: -4px;
	top: calc(50% - 3px);
	cursor: ew-resize;
}
.bottom-middle {
	bottom: -4px;
	left: calc(50% - 3px);
	cursor: ns-resize;
}
.bottom-left {
	left: -4px;
	bottom: -4px;
	cursor: nesw-resize;
}
.bottom-right {
	right: -4px;
	bottom: -4px;
	cursor: nwse-resize;
}
</style>
