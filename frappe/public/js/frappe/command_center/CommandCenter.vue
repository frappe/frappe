<template>
	<div>
		<input
			v-if="store.currentAction"
			id="command-center-search"
			type="text"
			class="form-control"
			placeholder="Search Doctype"
			autocomplete="off"
			@keydown="filterResult"
		/>
		<div class="command-center-menu" v-else>
			<button
				class="command-center-menu-item form-control"
				data-action="view"
				@click="store.currentAction = 'view'"
			>
				<div
					class="command-center-menu-icon"
					v-html="frappe.utils.icon('es-line-preview')"
				></div>
				<div class="command-center-menu-label">
					<span class="bold">V</span>{{ __("iew") }}
				</div>
			</button>
			<button
				class="command-center-menu-item form-control"
				data-action="create"
				@click="store.currentAction = 'create'"
			>
				<div
					class="command-center-menu-icon"
					v-html="frappe.utils.icon('es-line-add')"
				></div>
				<div class="command-center-menu-label">
					<span class="bold">C</span>{{ __("reate") }}
				</div>
			</button>
			<button
				class="command-center-menu-item form-control"
				data-action="edit"
				@click="store.currentAction = 'edit'"
			>
				<div
					class="command-center-menu-icon"
					v-html="frappe.utils.icon('es-line-edit')"
				></div>
				<div class="command-center-menu-label">
					<span class="bold">E</span>{{ __("dit") }}
				</div>
			</button>
			<button
				class="command-center-menu-item form-control"
				data-action="chart"
				@click="store.currentAction = 'report'"
			>
				<div
					class="command-center-menu-icon"
					v-html="frappe.utils.icon('es-line-chart')"
				></div>
				<div class="command-center-menu-label">
					<span class="bold">R</span>{{ __("eports") }}
				</div>
			</button>
			<!-- <button class="command-center-menu-item form-control" data-action="settings" @click="store.currentAction = 'settings'">
				<div class="command-center-menu-icon" v-html="frappe.utils.icon('es-line-settings')">
				</div>
				<div class="command-center-menu-label"><span class="bold">S</span>{{__("eports")}}</div>
			</button> -->
		</div>
		<div v-if="store.currentAction" class="create-list">
			<button
				class="form-control list-item"
				v-for="doc in list"
				:key="doc"
				@click="handleClick(doc)"
			>
				<span>{{ doc }}</span>
				<kbd>{{
					doc
						.split(" ")
						.map((l) => l[0])
						.join(" + ")
				}}</kbd>
			</button>
		</div>
	</div>
</template>

<script setup>
import { onMounted, watch, ref, nextTick } from "vue";
import { useCommandCenterStore } from "./store";
import { useDebounceFn } from "@vueuse/core";
const keyPressed = ref("");

const handleClick = (doctype) => {
	if (store.currentAction == "create") {
		frappe.new_doc(doctype);
	} else if (store.currentAction == "view") {
		frappe.set_route("List", doctype);
	} else if (store.currentAction == "report") {
		frappe.set_route("query-report", doctype);
	}
};

const keyPressedRegular = (e) => {
	keyPressed.value += e.key;
	debouncedKeyPress();
};

const debouncedKeyPress = useDebounceFn(() => {
	const doctypes = frappe.boot.command_center_shortcuts.filter(
		(s) => s.doctype_name == "DocType"
	);
	const reports = frappe.boot.command_center_shortcuts.filter((s) => s.doctype_name == "Report");
	if (store.currentAction == "report") {
		reports.forEach((shortcut) => {
			if (shortcut.shortcut_keys.toLowerCase() == keyPressed.value.toLowerCase()) {
				handleClick(shortcut.action);
				keyPressed.value = "";
				return;
			}
		});
	} else {
		doctypes.forEach((shortcut) => {
			if (shortcut.shortcut_keys.toLowerCase() == keyPressed.value.toLowerCase()) {
				handleClick(shortcut.action);
				keyPressed.value = "";
				return;
			}
		});
	}
	keyPressed.value = "";
}, 1000);

const props = defineProps({
	dialog: Object,
});
const list = ref([]);
const store = useCommandCenterStore();
onMounted(() => {
	list.value = frappe.boot.user.can_create;
	props.dialog.$wrapper.on("hidden.bs.modal", (e) => {
		store.currentAction = null;
		keyPressed.value = "";
		list.value = frappe.boot.user.can_create;
	});
	props.dialog.$wrapper.on("keydown", (e) => {
		if (e.ctrlKey || e.metaKey || e.altKey) {
			return;
		}
		e.stopPropagation();
		if (e.key === "Escape") {
			e.preventDefault();
			if (store.currentAction) {
				store.currentAction = null;
			} else {
				props.dialog.hide();
			}
		}
		if (store.currentAction) {
			keyPressedRegular(e);
			return;
		}

		if (e.key === "c") {
			store.currentAction = "create";
		} else if (e.key === "v") {
			store.currentAction = "view";
		} else if (e.key === "e") {
			store.currentAction = "edit";
		} else if (e.key === "r") {
			store.currentAction = "report";
		}
	});
	// commandCenterMenu.addEventListener('click', (e) => {
	//     const action = e.target.getAttribute('data-action');
	//     if (action) {
	//         frappe.commandCenter[action]();
	//     }
	// });
});

const filterResult = (e) => {
	const search = e.target.value;
	if (search) {
		const filteredList = frappe.boot.user.can_create.filter((doc) =>
			doc.toLowerCase().includes(search.toLowerCase())
		);
		list.value = filteredList;
	} else {
		list.value = frappe.boot.user.can_create;
	}
};

watch(
	() => store.currentAction,
	(newVal) => {
		if (newVal == "view") {
			props.dialog.set_title("View Documents");
			list.value = frappe.boot.user.can_create;
		} else if (newVal == "create") {
			props.dialog.set_title("Create New Document");
			list.value = frappe.boot.user.can_create;
			// nextTick(() => {
			//     setTimeout(() => {
			//         // props.dialog.$wrapper.find(".modal-body .ui-front").focus();
			//         // document.getElementById("command-center-search").focus();
			//     }, 800);
			// });
		} else if (newVal == "edit") {
			props.dialog.set_title("Edit Document");
			list.value = frappe.boot.user.can_create;
		} else if (newVal == "report") {
			props.dialog.set_title("View Reports");
			list.value = Object.keys(frappe.boot.user.all_reports);
		} else {
			props.dialog.set_title("Command Center");
		}
	}
);
</script>

<style lang="scss">
#command-center-search {
	padding: var(--padding-lg);
	border-bottom: 1px solid var(--border-color);
	margin: var(--margin-md) auto;
}
.command-center-menu {
	display: flex;
	flex-direction: row;
	gap: 10px;
}
.command-center-menu-item,
.create-list .list-item {
	display: flex;
	align-items: center;
	padding: var(--padding-lg);
	cursor: pointer;
	margin: 5px auto;
	transition: background-color 0.3s;
	background-color: var(--subtle-accent);
}
.command-center-menu-icon {
	margin-right: 10px;
}
.create-list {
	display: flex;
	flex-direction: column;
	flex-wrap: wrap;
	gap: 10px;
	margin: 10px auto;

	.list-item {
		justify-content: space-between;
	}
}
</style>
