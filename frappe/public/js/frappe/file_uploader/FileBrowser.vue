<template>
	<div class="file-browser">
		<div>
			<a href="" class="text-muted text-medium" @click.prevent="emit('hide-browser')">
				{{ __("← Back to upload files") }}
			</a>
		</div>
		<div class="file-browser-list">
			<div class="file-filter">
				<input
					type="search"
					class="form-control input-xs"
					:placeholder="__('Search by filename or extension')"
					v-model="search_text"
					@input="frappe.utils.debounce(search_by_name(), 300)"
				/>
			</div>
			<TreeNode
				class="tree with-skeleton"
				:node="node"
				:selected_node="selected_node"
				@node-click="(n) => toggle_node(n)"
				@load-more="(n) => load_more(n)"
			/>
		</div>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import TreeNode from "./TreeNode.vue";

// emits
let emit = defineEmits(["hide-browser"]);

// variables
let node = ref({
	label: __("Home"),
	value: "Home",
	children: [],
	children_start: 0,
	children_loading: false,
	is_leaf: false,
	fetching: false,
	fetched: false,
	open: false,
	filtered: true,
});
let selected_node = ref({});
let search_text = ref("");
let page_length = ref(10);
let folder_node = ref(null);

// methods
function toggle_node(node) {
	if (!node.fetched && !node.is_leaf) {
		node.fetching = true;
		node.children_start = 0;
		node.children_loading = false;
		get_files_in_folder(node.value, 0).then(({ files, has_more }) => {
			node.open = true;
			node.children = files;
			node.fetched = true;
			node.fetching = false;
			node.children_start += page_length.value;
			node.has_more_children = has_more;
		});
	} else {
		node.open = !node.open;
		select_node(node);
	}
}
function load_more(node) {
	if (node.has_more_children) {
		let start = node.children_start;
		node.children_loading = true;
		get_files_in_folder(node.value, start).then(({ files, has_more }) => {
			node.children = node.children.concat(files);
			node.children_start += page_length.value;
			node.has_more_children = has_more;
			node.children_loading = false;
		});
	}
}
function select_node(node) {
	if (node.is_leaf) {
		selected_node.value = node;
	}
}
function get_files_in_folder(folder, start) {
	return frappe
		.call("frappe.core.api.file.get_files_in_folder", {
			folder,
			start,
			page_length: page_length.value,
		})
		.then((r) => {
			let { files = [], has_more = false } = r.message || {};
			files.sort((a, b) => {
				if (a.is_folder && b.is_folder) {
					return a.modified < b.modified ? -1 : 1;
				}
				if (a.is_folder) {
					return -1;
				}
				if (b.is_folder) {
					return 1;
				}
				return 0;
			});
			files = files.map((file) => make_file_node(file));
			return { files, has_more };
		});
}
function search_by_name() {
	if (search_text.value === "") {
		node.value = folder_node.value;
		return;
	}
	if (search_text.value.length < 3) return;
	frappe
		.call("frappe.core.api.file.get_files_by_search_text", {
			text: search_text.value,
		})
		.then((r) => {
			let files = r.message || [];
			files = files.map((file) => make_file_node(file));
			if (!folder_node.value) {
				folder_node.value = node.value;
			}
			node.value = {
				label: __("Search Results"),
				value: "",
				children: files,
				by_search: true,
				open: true,
				filtered: true,
			};
		});
}
function make_file_node(file) {
	let filename = file.file_name || file.name;
	let label = frappe.utils.file_name_ellipsis(filename, 40);
	return {
		label: label,
		filename: filename,
		file_url: file.file_url,
		value: file.name,
		is_leaf: !file.is_folder,
		fetched: !file.is_folder, // fetched if node is leaf
		children: [],
		children_loading: false,
		children_start: 0,
		open: false,
		fetching: false,
		filtered: true,
	};
}

// mounted
onMounted(() => {
	toggle_node(node.value);
});

defineExpose({ selected_node });
</script>

<style scoped>
.file-browser-list {
	height: 300px;
	overflow: hidden;
	margin-top: 10px;
}

.file-filter {
	padding: 3px;
}

.tree {
	overflow: auto;
	height: 100%;
	padding-left: 0;
	padding-right: 0;
	padding-bottom: 4rem;
}
</style>
