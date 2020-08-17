<template>
	<div class="file-browser">
		<div>
			<a
				href=""
				class="text-muted text-medium"
				@click.prevent="$emit('hide-browser')"
			>{{ __('← Back to upload files') }}</a>
		</div>
		<div class="file-browser-list border rounded">
			<div class="file-filter">
				<input
					type="text"
					class="form-control input-xs"
					:placeholder="__('Search by filename or extension')"
					v-model="filter_text"
					@input="apply_filter"
				>
			</div>
			<TreeNode
				class="tree with-skeleton"
				:node="node"
				:selected_node="selected_node"
				@node-click="n => toggle_node(n)"
			/>
		</div>
	</div>
</template>
<script>
import TreeNode from "./TreeNode.vue";

// https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types
const restriction_mime_map = {
	'image/*': ['image/png', 'image/jpeg', 'image/gif'],
	'video/*': ['video/mpeg', 'video/ogg', 'video/mp2t', 'video/webm', 'video/3gpp'],
	'application/*': ['application/pdf', 'application/msword',
			'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
			'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			'application/vnd.oasis.opendocument.text', 'application/vnd.oasis.opendocument.spreadsheet'],
	'.pdf': ['application/pdf']
};

export default {
	name: 'FileBrowser',
	components: {
		TreeNode
	},
	props: ["restrictions"],
	data() {
		return {
			node: {
				label: __('Home'),
				value: 'Home',
				children: [],
				is_leaf: false,
				fetching: false,
				fetched: false,
				open: false,
				filtered: true
			},
			selected_node: {},
			filter_text: ''
		}
	},
	mounted() {
		this.toggle_node(this.node);
	},
	methods: {
		toggle_node(node) {
			if (!node.fetched && !node.is_leaf) {
				node.fetching = true;
				this.get_files_in_folder(node.value)
					.then(files => {
						node.open = true;
						node.children = files;
						node.fetched = true;
						node.fetching = false;
					});
			} else {
				node.open = !node.open;
				this.select_node(node);
			}
		},
		select_node(node) {
			if (node.is_leaf) {
				this.selected_node = node;
			}
		},
		get_files_in_folder(folder) {
			return frappe.call('frappe.core.doctype.file.file.get_files_in_folder', {
					folder: folder,
					restrict_mimetypes: this.get_restrictions()
				}).then(r => {
					let files = r.message || [];
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
					return files.map(file => {
						let filename = file.file_name || file.name;
						return {
							label: frappe.utils.file_name_ellipsis(filename, 40),
							filename: filename,
							file_url: file.file_url,
							value: file.name,
							is_leaf: !file.is_folder,
							fetched: !file.is_folder, // fetched if node is leaf
							children: [],
							open: false,
							fetching: false,
							filtered: true
						}
					});
				});
		},
		get_restrictions() {
			console.log(this.restrictions)
			let restrictions = []
			this.restrictions.allowed_file_types.forEach(res => {
				restrictions = restrictions.concat(restriction_mime_map[res])
			})

			console.log(restrictions);

			return restrictions
		},
		apply_filter: frappe.utils.debounce(function() {
			let filter_text = this.filter_text.toLowerCase();
			let apply_filter = (node) => {
				let search_string = node.filename.toLowerCase();
				if (node.is_leaf) {
					node.filtered = search_string.includes(filter_text);
				} else {
					node.children.forEach(apply_filter);
				}
			}
			this.node.children.forEach(apply_filter);
		}, 300)
	}
}
</script>

<style>
.file-browser-list {
	height: 300px;
	overflow: auto;
	margin-top: 10px;
}

.file-filter {
	padding: 15px 15px 0;
}
</style>
