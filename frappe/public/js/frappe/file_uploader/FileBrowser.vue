<template>
	<div class="file-browser">
		<div>
			<a
				href=""
				class="text-muted text-medium"
				@click.prevent="$emit('hide-browser')"
			>
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
					@input="search_by_name"
				/>
			</div>
			<TreeNode
				class="tree with-skeleton"
				:node="node"
				:selected_node="selected_node"
				@node-click="n => toggle_node(n)"
				@load-more="n => load_more(n)"
			/>
		</div>
	</div>
</template>
<script>
import TreeNode from "./TreeNode.vue";

export default {
	name: "FileBrowser",
	components: {
		TreeNode
	},
	data() {
		return {
			node: {
				label: __("Home"),
				value: "Home",
				children: [],
				children_start: 0,
				children_loading: false,
				is_leaf: false,
				fetching: false,
				fetched: false,
				open: false,
				filtered: true
			},
			selected_node: {},
			search_text: "",
			page_length: 10
		};
	},
	mounted() {
		this.toggle_node(this.node);
	},
	methods: {
		toggle_node(node) {
			if (!node.fetched && !node.is_leaf) {
				node.fetching = true;
				node.children_start = 0;
				node.children_loading = false;
				this.get_files_in_folder(node.value, 0).then(
					({ files, has_more }) => {
						node.open = true;
						node.children = files;
						node.fetched = true;
						node.fetching = false;
						node.children_start += this.page_length;
						node.has_more_children = has_more;
					}
				);
			} else {
				node.open = !node.open;
				this.select_node(node);
			}
		},
		load_more(node) {
			if (node.has_more_children) {
				let start = node.children_start;
				node.children_loading = true;
				this.get_files_in_folder(node.value, start).then(
					({ files, has_more }) => {
						node.children = node.children.concat(files);
						node.children_start += this.page_length;
						node.has_more_children = has_more;
						node.children_loading = false;
					}
				);
			}
		},
		select_node(node) {
			if (node.is_leaf) {
				this.selected_node = node;
			}
		},
		get_files_in_folder(folder, start) {
			return frappe
				.call("frappe.core.doctype.file.file.get_files_in_folder", {
					folder,
					start,
					page_length: this.page_length
				})
				.then(r => {
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
					files = files.map(file => this.make_file_node(file));
					return { files, has_more };
				});
		},
		search_by_name: frappe.utils.debounce(function() {
			if (this.search_text === "") {
				this.node = this.folder_node;
				return;
			}
			if (this.search_text.length < 3) return;
			frappe
				.call(
					"frappe.core.doctype.file.file.get_files_by_search_text",
					{
						text: this.search_text
					}
				)
				.then(r => {
					let files = r.message || [];
					files = files.map(file => this.make_file_node(file));
					if (!this.folder_node) {
						this.folder_node = this.node;
					}
					this.node = {
						label: __("Search Results"),
						value: "",
						children: files,
						by_search: true,
						open: true,
						filtered: true
					};
				});
		}, 300),
		make_file_node(file) {
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
				filtered: true
			};
		}
	}
};
</script>

<style>
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
