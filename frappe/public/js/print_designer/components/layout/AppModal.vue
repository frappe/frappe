<template>
	<Teleport to="#body" v-if="openModal">
		<div
			:ref="
				(el) => {
					MainStore.modal = { DOMRef: el };
				}
			"
			class="modal-dialog modal-sm"
			:style="[{ 'min-width': width, 'max-width': width, left, top }]"
		>
			<div class="modal-content">
				<div class="modal-header">
					<p class="modal-title"><slot name="title"></slot></p>
					<button
						class="btn btn-modal-close btn-link"
						data-dismiss="modal"
						@click="$emit('cancelClick')"
					>
						<svg class="icon icon-sm" style="font-size: 10px">
							<use class="close-alt" href="#icon-close-alt"></use>
						</svg>
					</button>
					<div class="modal-actions"></div>
				</div>
				<div
					class="modal-body ui-front"
					:style="[{ 'min-height': height, 'max-height': height }]"
				>
					<div class="hide modal-message"></div>
					<slot name="body"></slot>
				</div>
				<div class="modal-footer show">
					<button
						type="button"
						class="btn btn-primary btn-sm show btn-modal-primary"
						@click="$emit('primaryClick')"
					>
						Confirm
					</button>
					<button
						type="button"
						class="btn btn-default btn-sm show btn-modal-default"
						@click="$emit('cancelClick')"
					>
						Cancel
					</button>
				</div>
			</div>
		</div>
		<div
			class="modal fade search-dialog show"
			v-if="backdrop"
			style="
				overflow: auto;
				display: block;
				padding-left: 6px;
				z-index: 1021;
				background-color: rgb(152 161 169 / 0.75);
			"
			aria-modal="true"
		></div>
	</Teleport>
</template>

<script setup>
import { useDraggable } from "../../composables/Draggable";
import { useMainStore } from "../../store/MainStore";
import { useElementStore } from "../../store/ElementStore";
import { onMounted, watchPostEffect, toRefs } from "vue";
const MainStore = useMainStore();
const ElementStore = useElementStore();
const props = defineProps(["openModal", "size", "backdrop", "isDraggable"]);
const { width, height, top, left } = props.size;
defineEmits(["primaryClick", "cancelClick"]);
onMounted(() => {
	watchPostEffect(() => {
		if (props.openModal && props.isDraggable) {
			useDraggable({
				element: MainStore.modal,
				restrict: "#body",
				dragStartListener: (e) => {
					e.target.style.left = MainStore.modalLocation.x + "px";
					e.target.style.top = MainStore.modalLocation.y + "px";
				},
				dragMoveListener: (e) => {
					MainStore.modalLocation.isDragged = true;
					e.target.style.top =
						(parseFloat(e.target.style.top) || e.target.getBoundingClientRect().top) +
						e.delta.y +
						"px";
					e.target.style.left =
						(parseFloat(e.target.style.left) ||
							e.target.getBoundingClientRect().left) +
						e.delta.x +
						"px";
				},
				dragStopListener: (e) => {
					MainStore.modalLocation.x = parseFloat(e.target.style.left);
					MainStore.modalLocation.y = parseFloat(e.target.style.top);
				},
			});
		}
	});
});
</script>
<style lang="scss" scoped>
.modal-dialog {
	display: flex;
	font-size: 0.75rem;
	position: absolute;
	margin: 0;
	z-index: 1022;

	.modal-header {
		padding: 0;
		margin: 4px 0px 6px 0px;
		align-items: center;

		.modal-title {
			flex: 1;
			user-select: none;
			font-size: 13px;
			font-weight: 500;
			margin-left: 20px;
		}
	}
	.modal-body {
		user-select: none;
		padding: 0.5rem;
	}
	.modal-content {
		border: 1px solid rgba(0, 0, 0, 0.05);
	}
	.modal-footer {
		padding: 0.25rem 0.75rem;
		flex-direction: row-reverse;
		justify-content: flex-start;
		align-items: center;
	}
}
.results-area {
	max-height: min(80vh, 650px);
	overflow: auto;
}
.results-area::-webkit-scrollbar,
.overlay-sidebar::-webkit-scrollbar {
	width: 5px;
	height: 5px;
}
.results-area::-webkit-scrollbar-thumb,
.overlay-sidebar::-webkit-scrollbar-thumb {
	background: var(--gray-200);
	border-radius: 6px;
}
.results-area {
	max-height: min(80vh, 650px);
	overflow: auto;
}
.results-area::-webkit-scrollbar-track,
.results-area::-webkit-scrollbar-corner {
	background: white;
}
.overlay-sidebar::-webkit-scrollbar-track,
.overlay-sidebar::-webkit-scrollbar-corner {
	background: var(--bg-color);
}
.layout-side-section {
	background-color: var(--bg-color);
	overflow: hidden;
}
.search-dialog .search-results .results-summary {
	padding-top: var(--padding-sm);
}

.search-dialog .search-results .search-sidebar .standard-sidebar-item {
	margin-right: var(--padding-sm);
}

/* .search-dialog .search-results .search-sidebar {
    max-height: 100vh;
} */
.result-title {
	display: flex;
	font-size: 2em;
	font-weight: 800;
	padding: 6px 0px;
	margin-left: 0;
}
.result:hover,
.result:active {
	background-color: var(--gray-200);
	border-radius: var(--border-radius);
}
.result-section-link:hover,
.result-section-link:active {
	color: var(--dark);
}
.result-title:not(:first-child) {
	padding-top: 1em;
}
</style>
