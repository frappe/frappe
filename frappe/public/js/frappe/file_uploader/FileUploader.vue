<template>
	<div class="file-uploader"
		@dragover.prevent="dragover"
		@dragleave.prevent="dragleave"
		@drop.prevent="dropfiles"
	>
		<div
			class="file-upload-area padding border rounded text-center cursor-pointer flex align-center justify-center"
			@click="browse_files"
			v-show="files.length === 0 && !show_file_browser"
		>
			<div v-if="!is_dragging">
				<div>
					{{ __('Drag and drop files, ') }}
					<label style="margin: 0">
						<a href="#" class="text-primary" @click.prevent>{{ __('browse') }}</a>
						<input
							type="file"
							class="hidden"
							ref="file_input"
							@change="on_file_input"
							:multiple="multiple_files"
						>
					</label>
					{{ __('or choose an') }}
					<a href="#" class="text-primary bold"
						@click.stop.prevent="show_file_browser = true"
					>
						{{ __('uploaded file') }}
					</a>
				</div>
			</div>
			<div v-else>
				{{ __('Drop files here') }}
			</div>
		</div>
		<div class="file-preview-area" v-show="files.length && !show_file_browser">
			<div class="margin-bottom" v-if="!upload_complete">
				<label>
					<input type="checkbox" class="input-with-feedback" @change="e => toggle_all_private(e.target.checked)">
					<span class="text-medium" style="font-weight: normal;">
						{{ __('Make all attachments private') }}
					</span>
				</label>
			</div>
			<div class="flex flex-wrap">
				<FilePreview
					v-for="(file, i) in files"
					:key="file.name"
					:file="file"
					@remove="remove_file(i)"
					@toggle_private="toggle_private(i)"
				/>
			</div>
			<button
				v-if="show_upload_button && currently_uploading === -1"
				class="btn btn-primary btn-sm margin-top"
				@click="upload_files"
			>
				<span v-if="files.length === 1">
					{{ __('Upload file') }}
				</span>
				<span v-else>
					{{ __('Upload {0} files', [files.length]) }}
				</span>
			</button>
		</div>
		<div class="upload-progress" v-if="currently_uploading !== -1 && !upload_complete && !show_file_browser">
			<span
				class="text-medium"
				v-html="__('Uploading {0} of {1}', [String(currently_uploading + 1).bold(), String(files.length).bold()])"
			>
			</span>
			<div
				class="progress"
				:key="i"
				v-for="(file, i) in files"
				v-show="currently_uploading===i"
			>
				<div
					class="progress-bar"
					:class="[file.total - file.progress < 20 ? 'progress-bar-success' : 'progress-bar-warning']"
					role="progressbar"
					:aria-valuenow="(file.progress * 100 / file.total)"
					aria-valuemin="0"
					aria-valuemax="100"
					:style="{'width': (file.progress * 100 / file.total) + '%' }"
				>
				</div>
			</div>
		</div>
		<FileBrowser
			ref="file_browser"
			v-if="show_file_browser"
			@hide-browser="show_file_browser = false"
		/>
	</div>
</template>

<script>
import FilePreview from './FilePreview.vue';
import FileBrowser from './FileBrowser.vue';

export default {
	name: 'FileUploader',
	props: {
		show_upload_button: {
			default: true
		},
		multiple_files: {
			default: true
		},
		doctype: {
			default: null
		},
		docname: {
			default: null
		},
		folder: {
			default: 'Home'
		},
		method: {
			default: null
		},
		on_success: {
			default: null
		}
	},
	components: {
		FilePreview,
		FileBrowser
	},
	data() {
		return {
			files: [],
			is_dragging: false,
			currently_uploading: -1,
			show_file_browser: false
		}
	},
	watch: {
		files(newvalue, oldvalue) {
			if (!this.multiple_files && newvalue.length > 1) {
				this.files = [newvalue[newvalue.length - 1]];
			}
		}
	},
	computed: {
		upload_complete() {
			return this.files.length > 0
				&& this.files.every(
					file => file.total !== 0 && file.progress === file.total);
		},
		upload_failed() {
			return this.files.length > 0 && this.files.every(file => file.failed);
		}
	},
	methods: {
		dragover() {
			this.is_dragging = true;
		},
		dragleave() {
			this.is_dragging = false;
		},
		dropfiles(e) {
			this.is_dragging = false;
			this.add_files(e.dataTransfer.files);
		},
		browse_files() {
			this.$refs.file_input.click();
		},
		on_file_input(e) {
			this.add_files(this.$refs.file_input.files);
		},
		remove_file(i) {
			this.files = this.files.filter((file, j) => i !== j);
		},
		toggle_private(i) {
			this.files[i].private = !this.files[i].private;
		},
		toggle_all_private(flag) {
			this.files = this.files.map(file => {
				file.private = flag;
				return file;
			});
		},
		add_files(file_array) {
			let files = Array.from(file_array).map(file => {
				let is_image = file.type.startsWith('image');
				return {
					file_obj: file,
					name: file.name,
					doc: null,
					progress: 0,
					total: 0,
					failed: false,
					uploading: false,
					private: !is_image
				}
			});
			this.files = this.files.concat(files);
		},
		upload_files() {
			if (this.show_file_browser) {
				let selected_file = this.$refs.file_browser.selected_node;
				if (!selected_file.value) {
					frappe.msgprint(__('Click on a file to select it.'));
					return Promise.reject();
				}

				return this.upload_file({
					file_url: selected_file.file_url
				});
			}
			return frappe.run_serially(
				this.files.map(
					(file, i) =>
						() => this.upload_file(file, i)
				)
			);
		},
		upload_file(file, i) {
			this.currently_uploading = i;

			return new Promise((resolve, reject) => {
				let xhr = new XMLHttpRequest();
				xhr.upload.addEventListener('loadstart', (e) => {
					file.uploading = true;
				})
				xhr.upload.addEventListener('progress', (e) => {
					if (e.lengthComputable) {
						file.progress = e.loaded;
						file.total = e.total;
					}
				})
				xhr.upload.addEventListener('load', (e) => {
					file.uploading = false;
					resolve();
				})
				xhr.addEventListener('error', (e) => {
					file.failed = true;
					reject();
				})
				xhr.onreadystatechange = () => {
					if (xhr.readyState == XMLHttpRequest.DONE) {
						if (xhr.status === 200) {
							let r = null;
							let doc = null;
							try {
								r = JSON.parse(xhr.responseText);
								if (r.message.doctype === 'File') {
									doc = r.message;
								}
							} catch(e) {
								r = xhr.responseText;
							}

							file.doc = doc;

							if (this.on_success) {
								this.on_success(r);
							}
						} else {
							file.failed = true;
							try {
								console.error(JSON.parse(xhr.responseText));
							} catch(e) {
								console.error(xhr.responseText);
							}
						}
					}
				}
				xhr.open('POST', '/api/method/upload_file', true);
				xhr.setRequestHeader('Accept', 'application/json');
				xhr.setRequestHeader('X-Frappe-CSRF-Token', frappe.csrf_token);

				let form_data = new FormData();
				if (file.file_obj) {
					form_data.append('file', file.file_obj, file.name);
				}
				form_data.append('is_private', +file.private);
				form_data.append('folder', this.folder);

				if (file.file_url) {
					form_data.append('file_url', file.file_url);
				}

				if (this.doctype && this.docname) {
					form_data.append('doctype', this.doctype);
					form_data.append('docname', this.docname);
				}

				if (this.method) {
					form_data.append('method', this.method);
				}

				xhr.send(form_data);
			});
		}
	}
}
</script>
<style>
.file-upload-area {
	min-height: 100px;
}
</style>
