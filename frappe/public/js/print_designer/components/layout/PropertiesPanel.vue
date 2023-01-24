<template>
	<div
		class="properties-container"
		:ref="
			(el) => {
				MainStore.propertiesContainer = el;
			}
		"
	>
		<div class="align-items-container" v-if="MainStore.getCurrentElementsId.length">
			<div class="horizontal-align-container">
				<div
					class="align-item-icon"
					@dblclick.stop
					@click="handleAlignIconClick($event, 'align-left')"
				>
					<AlignLeft />
				</div>
				<div
					class="align-item-icon"
					@dblclick.stop
					@click="handleAlignIconClick($event, 'align-horizontal-center')"
				>
					<HorizontalAlignCenter />
				</div>
				<div
					class="align-item-icon"
					@dblclick.stop
					@click="handleAlignIconClick($event, 'align-right')"
				>
					<AlignRight />
				</div>
			</div>
			<div class="vertical-align-container">
				<div
					class="align-item-icon"
					@dblclick.stop
					@click="handleAlignIconClick($event, 'align-top')"
				>
					<AlignTop />
				</div>
				<div
					class="align-item-icon"
					@dblclick.stop
					@click="handleAlignIconClick($event, 'align-vertical-center')"
				>
					<VerticalAlignCenter />
				</div>
				<div
					class="align-item-icon"
					@dblclick.stop
					@click="handleAlignIconClick($event, 'align-bottom')"
				>
					<AlignBottom />
				</div>
			</div>
		</div>
		<div class="transform-container" v-if="MainStore.getCurrentElementsId.length === 1">
			<p
				style="
					margin-top: 5px;
					margin-left: 15px;
					font-weight: 400;
					font-size: 12px;
					user-select: none;
				"
			>
				Transform
			</p>
			<div class="d-flex">
				<div class="d-flex mt-1">
					<label class="mx-1 main-label" for="propertiesWidthInput">W</label>
					<div class="input-group">
						<input
							:value="
								useChangeValueUnit({
									inputString: MainStore.getCurrentElementsValues[0].width,
									defaultInputUnit: 'px',
									convertionUnit: MainStore.page.UOM,
								}).value.toFixed(2) + ` ${MainStore.page.UOM}`
							"
							@blur="
								(e) => {
									e.stopImmediatePropagation();
									convertedValue = useChangeValueUnit({
										inputString: e.target.value,
										defaultInputUnit: MainStore.page.UOM,
									});
									if (convertedValue.error) {
										e.target.value =
											useChangeValueUnit({
												inputString:
													MainStore.getCurrentElementsValues[0].width,
												defaultInputUnit: 'px',
												convertionUnit: 'mm',
											}).value.toFixed(2) + ` ${MainStore.page.UOM}`;
									} else {
										MainStore.getCurrentElementsValues[0].width =
											convertedValue.value;
									}
								}
							"
							@keyup.stop.enter="
								($event) => {
									$event.target.blur();
								}
							"
							@keydown.stop
							@keyup.stop
							autocomplete="off"
							class="form-control mx-1 height-append"
							id="propertiesWidthInput"
							style="min-width: 50px"
						/>
					</div>
				</div>
				<div class="d-flex mt-1">
					<label class="mx-1 main-label" for="propertiesHeightInput">H</label>
					<div class="input-group">
						<input
							:value="
								useChangeValueUnit({
									inputString: MainStore.getCurrentElementsValues[0].height,
									defaultInputUnit: 'px',
									convertionUnit: 'mm',
								}).value.toFixed(2) + ` ${MainStore.page.UOM}`
							"
							@blur="
								(e) => {
									e.stopImmediatePropagation();
									MainStore.getCurrentElementsValues[0].height =
										useChangeValueUnit({
											inputString: e.target.value,
											defaultInputUnit: MainStore.page.UOM,
										}).value;
								}
							"
							@keyup.stop.enter="
								($event) => {
									$event.target.blur();
								}
							"
							@keydown.stop
							@keyup.stop
							autocomplete="off"
							class="form-control mx-1 height-append"
							id="propertiesWidthInput"
							style="min-width: 50px"
						/>
					</div>
				</div>
			</div>
			<div class="d-flex">
				<div class="d-flex mt-1">
					<label class="mx-1 main-label" for="propertiesWidthInput">X</label>
					<div class="input-group">
						<input
							:value="
								useChangeValueUnit({
									inputString: MainStore.getCurrentElementsValues[0].startX,
									defaultInputUnit: 'px',
									convertionUnit: 'mm',
								}).value.toFixed(2) + ` ${MainStore.page.UOM}`
							"
							@blur="
								(e) => {
									e.stopImmediatePropagation();
									MainStore.getCurrentElementsValues[0].startX =
										useChangeValueUnit({
											inputString: e.target.value,
											defaultInputUnit: MainStore.page.UOM,
										}).value;
								}
							"
							@keyup.stop.enter="
								($event) => {
									$event.target.blur();
								}
							"
							@keydown.stop
							@keyup.stop
							autocomplete="off"
							class="form-control mx-1 height-append"
							id="propertiesWidthInput"
							style="min-width: 50px"
						/>
					</div>
				</div>
				<div class="d-flex mt-1">
					<label class="mx-1 main-label" for="propertiesHeightInput">Y</label>
					<div class="input-group">
						<input
							:value="
								useChangeValueUnit({
									inputString: MainStore.getCurrentElementsValues[0].startY,
									defaultInputUnit: 'px',
									convertionUnit: 'mm',
								}).value.toFixed(2) + ` ${MainStore.page.UOM}`
							"
							@blur="
								(e) => {
									e.stopImmediatePropagation();
									MainStore.getCurrentElementsValues[0].startY =
										useChangeValueUnit({
											inputString: e.target.value,
											defaultInputUnit: MainStore.page.UOM,
										}).value;
								}
							"
							@keyup.stop.enter="
								($event) => {
									$event.target.blur();
								}
							"
							@keydown.stop
							@keyup.stop
							autocomplete="off"
							class="form-control mx-1 height-append"
							id="propertiesWidthInput"
							style="min-width: 50px"
						/>
					</div>
				</div>
			</div>
		</div>
		<div
			v-if="
				MainStore.getCurrentElementsValues.length === 0 &&
				MainStore.activeControl == 'text'
			"
		>
			<div class="text-type-container">
				<!-- <AppButton :isPrimary="MainStore.textControlType == 'static'">Static</AppButton>
				<AppButton :isPrimary="MainStore.textControlType == 'dynamic'">Dynamic</AppButton> -->
				<div
					class="text-type"
					:class="{ 'text-type-active': MainStore.textControlType == 'static' }"
					@click="MainStore.textControlType = 'static'"
				>
					Static
				</div>
				<div
					class="text-type"
					:class="{ 'text-type-active': MainStore.textControlType == 'dynamic' }"
					@click="MainStore.textControlType = 'dynamic'"
				>
					Dynamic
				</div>
			</div>
		</div>
		<div
			v-if="
				MainStore.getCurrentElementsValues.length === 1 &&
				MainStore.getCurrentElementsValues[0].type == 'text'
			"
		>
			StaticText
		</div>
		<div
			class="page-settings"
			v-show="
				MainStore.activeControl == 'mouse-pointer' &&
				!MainStore.getCurrentElementsId.length
			"
		>
			<p style="margin-left: 10px; font-weight: 400; font-size: 12px; user-select: none">
				Page Settings
			</p>
			<div
				class="documentSelector"
				@keydown.stop
				@keyup.stop
				:ref="refSelectDocumentControl"
			></div>
			<!-- <div
				class="mx-3 mt-1"
				style="
					margin-top: 5px;
					padding-bottom: 15px;
					border-bottom: 1px solid var(--border-color);
				"
			>
				<select
					:value="MainStore.currentPageSize"
					@change.stop="onPageChange"
					autocomplete="off"
					class="form-control mx-1 height-append"
					id="propertiesWidthInput"
					style="min-width: 50px"
				>
					<template v-for="(page, pagename) in MainStore.pageSizes">
						<option :selected="MainStore.currentPageSize" :value="pagename">
							{{ pagename }}
						</option>
					</template>
				</select>
				<select
					:value="MainStore.page.UOM"
					@change.stop="handleChangeUOM"
					autocomplete="off"
					class="form-control mt-3 mx-1 height-append"
					id="propertiesWidthInput"
					style="min-width: 50px"
				>
					<option selected="px" value="px">Pixels (px)</option>
					<option selected="mm" value="mm">Milimeter (mm)</option>
					<option selected="cm" value="cm">Centimeter (cm)</option>
					<option selected="in" value="in">Inch (in)</option>
				</select>
			</div> -->
			<div class="d-flex">
				<div class="d-flex mx-2 mt-1">
					<label class="mx-1 main-label" for="propertiesWidthInput">Width:</label>
					<div class="input-group">
						<input
							:value="
								useChangeValueUnit({
									inputString: MainStore.page.width,
									defaultInputUnit: MainStore.page.UOM,
									convertionUnit: MainStore.page.UOM,
								}).value.toFixed(2) + ` ${MainStore.page.UOM}`
							"
							@blur="
								(e) => {
									e.stopImmediatePropagation();
									MainStore.page.width = useChangeValueUnit({
										inputString: e.target.value,
										defaultInputUnit: MainStore.page.UOM,
										convertionUnit: MainStore.page.UOM,
									}).value;
								}
							"
							@keyup.stop.enter="
								($event) => {
									$event.target.blur();
								}
							"
							@keydown.stop
							@keyup.stop
							autocomplete="off"
							class="form-control mx-1 height-append"
							id="propertiesWidthInput"
							style="min-width: 50px"
						/>
					</div>
				</div>
				<div class="d-flex mx-2 mt-1">
					<label class="mx-1 main-label" for="propertiesHeightInput">Height:</label>
					<div class="input-group">
						<input
							:value="
								useChangeValueUnit({
									inputString: MainStore.page.height,
									defaultInputUnit: MainStore.page.UOM,
									convertionUnit: MainStore.page.UOM,
								}).value.toFixed(2) + ` ${MainStore.page.UOM}`
							"
							@blur="
								(e) => {
									e.stopImmediatePropagation();
									MainStore.page.height = useChangeValueUnit({
										inputString: e.target.value,
										defaultInputUnit: MainStore.page.UOM,
										convertionUnit: MainStore.page.UOM,
									}).value;
								}
							"
							@keyup.stop.enter="
								($event) => {
									$event.target.blur();
								}
							"
							@keydown.stop
							@keyup.stop
							autocomplete="off"
							class="form-control mx-1 height-append"
							id="propertiesWidthInput"
							style="min-width: 50px"
						/>
					</div>
				</div>
			</div>
			<div class="d-flex">
				<div class="d-flex mx-2 mt-1">
					<label class="mx-1 main-label" for="propertiesWidthInput">Top:</label>
					<div class="input-group">
						<input
							:value="
								useChangeValueUnit({
									inputString: MainStore.page.marginTop,
									defaultInputUnit: MainStore.page.UOM,
									convertionUnit: MainStore.page.UOM,
								}).value.toFixed(2) + ` ${MainStore.page.UOM}`
							"
							@blur="
								(e) => {
									e.stopImmediatePropagation();
									MainStore.page.marginTop = useChangeValueUnit({
										inputString: e.target.value,
										defaultInputUnit: MainStore.page.UOM,
										convertionUnit: MainStore.page.UOM,
									}).value;
								}
							"
							@keyup.stop.enter="
								($event) => {
									$event.target.blur();
								}
							"
							@keydown.stop
							@keyup.stop
							autocomplete="off"
							data-append="px"
							class="form-control mx-1 height-append"
							id="propertiesWidthInput"
							style="min-width: 50px"
						/>
					</div>
				</div>
				<div class="d-flex mx-2 mt-1">
					<label class="mx-1 main-label" for="propertiesHeightInput">Bottom:</label>
					<div class="input-group">
						<input
							:value="
								useChangeValueUnit({
									inputString: MainStore.page.marginBottom,
									defaultInputUnit: MainStore.page.UOM,
									convertionUnit: MainStore.page.UOM,
								}).value.toFixed(2) + ` ${MainStore.page.UOM}`
							"
							@blur="
								(e) => {
									e.stopImmediatePropagation();
									MainStore.page.marginBottom = useChangeValueUnit({
										inputString: e.target.value,
										defaultInputUnit: MainStore.page.UOM,
										convertionUnit: MainStore.page.UOM,
									}).value;
								}
							"
							@keyup.stop.enter="
								($event) => {
									$event.target.blur();
								}
							"
							@keydown.stop
							@keyup.stop
							autocomplete="off"
							data-append="px"
							class="form-control mx-1 height-append"
							id="propertiesWidthInput"
							style="min-width: 50px"
						/>
					</div>
				</div>
			</div>
			<div class="d-flex">
				<div class="d-flex mx-2 mt-1">
					<label class="mx-1 main-label" for="propertiesWidthInput">Left:</label>
					<div class="input-group">
						<input
							:value="
								useChangeValueUnit({
									inputString: MainStore.page.marginLeft,
									defaultInputUnit: MainStore.page.UOM,
									convertionUnit: MainStore.page.UOM,
								}).value.toFixed(2) + ` ${MainStore.page.UOM}`
							"
							@blur="
								(e) => {
									e.stopImmediatePropagation();
									MainStore.page.marginLeft = useChangeValueUnit({
										inputString: e.target.value,
										defaultInputUnit: MainStore.page.UOM,
										convertionUnit: MainStore.page.UOM,
									}).value;
								}
							"
							@keyup.stop.enter="
								($event) => {
									$event.target.blur();
								}
							"
							@keydown.stop
							@keyup.stop
							autocomplete="off"
							data-append="px"
							class="form-control mx-1 height-append"
							id="propertiesWidthInput"
							style="min-width: 50px"
						/>
					</div>
				</div>
				<div class="d-flex mx-2 mt-1">
					<label class="mx-1 main-label" for="propertiesHeightInput">Right:</label>
					<div class="input-group">
						<input
							:value="
								useChangeValueUnit({
									inputString: MainStore.page.marginRight,
									defaultInputUnit: MainStore.page.UOM,
									convertionUnit: MainStore.page.UOM,
								}).value.toFixed(2) + ` ${MainStore.page.UOM}`
							"
							@blur="
								(e) => {
									e.stopImmediatePropagation();
									MainStore.page.marginRight = useChangeValueUnit({
										inputString: e.target.value,
										defaultInputUnit: MainStore.page.UOM,
										convertionUnit: MainStore.page.UOM,
									}).value;
								}
							"
							@keyup.stop.enter="
								($event) => {
									$event.target.blur();
								}
							"
							@keydown.stop
							@keyup.stop
							autocomplete="off"
							data-append="px"
							class="form-control mx-1 height-append"
							id="propertiesWidthInput"
							style="min-width: 50px"
						/>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import { useMainStore } from "../../store/MainStore";
import AlignTop from "../../icons/AlignTop.vue";
import VerticalAlignCenter from "../../icons/VerticalAlignCenter.vue";
import AlignBottom from "../../icons/AlignBottom.vue";
import AlignLeft from "../../icons/AlignLeft.vue";
import HorizontalAlignCenter from "../../icons/HorizontalAlignCenter.vue";
import AlignRight from "../../icons/AlignRight.vue";
import { useChangeValueUnit } from "../../composables/ChangeValueUnit";
import { refSelectDocumentControl } from "../../frappeControls";
const MainStore = useMainStore();
const handleAlignIconClick = (e, value) => {
	let currentElements = MainStore.getCurrentElementsValues;
	if (currentElements.length == 1) {
		switch (value) {
			case "align-top":
				MainStore.getCurrentElementsValues.forEach((element) => {
					element.startY = 0;
				});
				break;
			case "align-vertical-center":
				MainStore.getCurrentElementsValues.forEach((element) => {
					element.startY =
						(useChangeValueUnit({
							inputString:
								MainStore.page.height -
								MainStore.page.marginTop -
								MainStore.page.marginBottom,
							defaultInputUnit: MainStore.page.UOM,
						}).value -
							useChangeValueUnit({ inputString: element.height }).value) /
						2;
				});
				break;
			case "align-bottom":
				MainStore.getCurrentElementsValues.forEach((element) => {
					element.startY =
						useChangeValueUnit({
							inputString:
								MainStore.page.height -
								MainStore.page.marginTop -
								MainStore.page.marginBottom,
							defaultInputUnit: MainStore.page.UOM,
						}).value - useChangeValueUnit({ inputString: element.height }).value;
				});
				break;
			case "align-left":
				MainStore.getCurrentElementsValues.forEach((element) => {
					element.startX = 0;
				});
				break;
			case "align-horizontal-center":
				MainStore.getCurrentElementsValues.forEach((element) => {
					element.startX =
						(useChangeValueUnit({
							inputString:
								MainStore.page.width -
								MainStore.page.marginLeft -
								MainStore.page.marginRight,
							defaultInputUnit: MainStore.page.UOM,
						}).value -
							useChangeValueUnit({ inputString: element.width }).value) /
						2;
				});
				break;
			case "align-right":
				MainStore.getCurrentElementsValues.forEach((element) => {
					element.startX =
						useChangeValueUnit({
							inputString:
								MainStore.page.width -
								MainStore.page.marginLeft -
								MainStore.page.marginRight,
							defaultInputUnit: MainStore.page.UOM,
						}).value - useChangeValueUnit({ inputString: element.width }).value;
				});
				break;
		}
	} else if (currentElements.length > 1) {
		const parentRect = MainStore.mainContainer.getBoundingClientRect();
		let offsetRect = MainStore.getCurrentElementsValues.reduce(
			(offset, currentElement) => {
				let currentElementRect = currentElement.DOMRef.getBoundingClientRect();
				currentElementRect.left < offset.left && (offset.left = currentElementRect.left);
				currentElementRect.top < offset.top && (offset.top = currentElementRect.top);
				currentElementRect.right > offset.right &&
					(offset.right = currentElementRect.right);
				currentElementRect.bottom > offset.bottom &&
					(offset.bottom = currentElementRect.bottom);
				return offset;
			},
			{ left: 9999, top: 9999, right: 0, bottom: 0 }
		);
		(offsetRect.top -= parentRect.top), (offsetRect.left -= parentRect.left);
		(offsetRect.right -= parentRect.left), (offsetRect.bottom -= parentRect.top);
		switch (value) {
			case "align-top":
				MainStore.getCurrentElementsValues.forEach((element) => {
					element.startY = offsetRect.top;
				});
				break;
			case "align-vertical-center":
				MainStore.getCurrentElementsValues.forEach((element) => {
					element.startY =
						offsetRect.top +
						(offsetRect.bottom - offsetRect.top) / 2 -
						element.height / 2;
				});
				break;
			case "align-bottom":
				MainStore.getCurrentElementsValues.forEach((element) => {
					element.startY = offsetRect.bottom - element.height;
				});
				break;
			case "align-left":
				MainStore.getCurrentElementsValues.forEach((element) => {
					element.startX = offsetRect.left;
				});
				break;
			case "align-horizontal-center":
				MainStore.getCurrentElementsValues.forEach((element) => {
					element.startX =
						offsetRect.left +
						(offsetRect.right - offsetRect.left) / 2 -
						element.width / 2;
				});
				break;
			case "align-right":
				MainStore.getCurrentElementsValues.forEach((element) => {
					element.startX = offsetRect.right - element.width;
				});
				break;
		}
	}
	e.stopPropagation();
};
</script>
<style deep lang="scss">
.documentSelector {
	.awesomplete > ul {
		min-width: 210px;
	}
	.clearfix {
		display: none;
	}
}
</style>
<style scoped lang="scss">
* {
	user-select: none;
}
.text-type-container {
	display: flex;
	justify-content: center;
	align-items: center;
	background-color: var(--bg-color);

	.text-type {
		padding: 6px 16px;
		margin: 6px 0px;
	}

	.text-type-active {
		background-color: white;
		box-shadow: var(--card-shadow);
		border-radius: var(--border-radius);
	}
}
.transform-container {
	border-top: 1px solid var(--border-color);
	border-bottom: 1px solid var(--border-color);
	margin: 0px 10px;
	padding: 8px 0px;
}

.d-flex > .input-group {
	user-select: none;
}
.d-flex > .main-label {
	font-size: 10px;
	vertical-align: middle;
	font-weight: 500;
}
.d-flex > .input-group > input {
	background-color: var(--fg-color);
	border-bottom: 1px solid var(--gray-300);
	border-radius: 0px;
}
.d-flex > .input-group > input:focus {
	box-shadow: none;
	border-bottom-color: var(--primary-color);
}
.d-flex > .input-group > label:after {
	left: 70px;
	font-size: 11px;
}
.horizontal-align-container {
	display: flex;
	width: 50%;
	justify-content: space-around;
}
.vertical-align-container {
	display: flex;
	width: 50%;
	border-left: 1px solid var(--border-color);
	justify-content: space-around;
}
.align-item-icon {
	height: 24px;
	width: 24px;
	fill: var(--text-muted);
}
.align-items-container {
	padding: 8px 10px;
	display: flex;
	background-color: var(--fg-color);
}
hr {
	margin: 10px 0px;
}
.properties-container {
	position: relative;
}
.page-settings {
	padding: 8px 10px;
	border-bottom: 1px solid var(--border-color);

	.d-flex.mx-2.mt-1 {
		flex-direction: column;
	}
	.d-flex > .main-label {
		font-size: 11px;
		vertical-align: middle;
		font-weight: 500;
	}
}
.page-settings > p {
	margin-top: 5px;
	margin-bottom: 15px;
}
label {
	user-select: none;
	position: relative;
	display: block;
	font-size: 11px;
	box-sizing: border-box;
	font-weight: 400;
}
input {
	position: relative;
	display: block;
	font-size: 11px;
	box-sizing: border-box;
}

.main-label {
	margin-top: 10px;
}
</style>
