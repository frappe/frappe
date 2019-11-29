<template>
	<div class="file-uploader"
		@dragover.prevent="dragover"
		@dragleave.prevent="dragleave"
		@drop.prevent="dropfiles"
	>
		<div
			class="file-upload-area padding border rounded text-center cursor-pointer flex align-center justify-center"
			@click="browse_files"
			v-show="files.length === 0 && !show_file_browser && !show_web_link"
		>
			<div v-if="!is_dragging">
				<div>
					{{ __('Drag and drop files, ') }}
					<label style="margin: 0">
						<a href="#" class="text-primary" @click.prevent>{{ __('browse,') }}</a>
						<input
							type="file"
							class="hidden"
							ref="file_input"
							@change="on_file_input"
							:multiple="allow_multiple"
							:accept="restrictions.allowed_file_types.join(', ')"
						>
					</label>
					<span v-if="!disable_file_browser">
						{{ __('choose an') }}
						<a href="#" class="text-primary bold"
							@click.stop.prevent="show_file_browser = true"
						>
							{{ __('uploaded file') }}
						</a>
					</span>
					{{ __('or attach a') }}
					<a class="text-primary bold" href
						@click.stop.prevent="show_web_link = true"
					>
						{{ __('web link') }}
					</a>
				</div>
				<div class="text-muted text-medium">
					{{ upload_notes }}
				</div>
			</div>
			<div v-else>
				{{ __('Drop files here') }}
			</div>
		</div>
		<div class="file-preview-area" v-show="files.length && !show_file_browser && !show_web_link">
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
			<div class="flex align-center" v-if="show_upload_button && currently_uploading === -1">
				<button
					class="btn btn-primary btn-sm margin-right"
					@click="upload_files"
				>
					<span v-if="files.length === 1">
						{{ __('Upload file') }}
					</span>
					<span v-else>
						{{ __('Upload {0} files', [files.length]) }}
					</span>
				</button>
				<div class="text-muted text-medium">
					{{ __('Click on the lock icon to toggle public/private') }}
				</div>
			</div>
		</div>
		<div class="upload-progress" v-if="currently_uploading !== -1 && !upload_complete && !show_file_browser && !show_web_link">
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
			v-if="show_file_browser && !disable_file_browser"
			@hide-browser="show_file_browser = false"
		/>
		<WebLink
			ref="web_link"
			v-if="show_web_link"
			@hide-web-link="show_web_link = false"
		/>
	</div>
</template>

<script>
import FilePreview from './FilePreview.vue';
import FileBrowser from './FileBrowser.vue';
import WebLink from './WebLink.vue';

export default {
	name: 'FileUploader',
	props: {
		show_upload_button: {
			default: true
		},
		disable_file_browser: {
			default: false
		},
		allow_multiple: {
			default: true
		},
		as_dataurl: {
			default: false
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
		},
		restrictions: {
			default: () => ({
				max_file_size: null, // 2048 -> 2KB
				max_number_of_files: null,
				allowed_file_types: [] // ['image/*', 'video/*', '.jpg', '.gif', '.pdf']
			})
		},
		upload_notes: {
			default: null // "Images or video, upto 2MB"
		}
	},
	components: {
		FilePreview,
		FileBrowser,
		WebLink
	},
	data() {
		return {
			files: [],
			is_dragging: false,
			currently_uploading: -1,
			show_file_browser: false,
			show_web_link: false,
		}
	},
	watch: {
		files(newvalue, oldvalue) {
			if (!this.allow_multiple && newvalue.length > 1) {
				this.files = [newvalue[newvalue.length - 1]];
			}
		}
	},
	computed: {
		upload_complete() {
			return this.files.length > 0
				&& this.files.every(
					file => file.total !== 0 && file.progress === file.total);
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
			let files = Array.from(file_array)
				.filter(this.check_restrictions)
				.map(file => {
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
		check_restrictions(file) {
			let { max_file_size, allowed_file_types } = this.restrictions;

			let mime_type = file.type;
			let extension = '.' + file.name.split('.').pop();

			let is_correct_type = true;
			let valid_file_size = true;

			if (allowed_file_types.length) {
				is_correct_type = allowed_file_types.some((type) => {
					// is this is a mime-type
					if (type.includes('/')) {
						if (!file.type) return false;
						return file.type.match(type);
					}

					// otherwise this is likely an extension
					if (type[0] === '.') {
						return file.name.endsWith(type);
					}
					return false;
				});
			}

			if (max_file_size && file.size != null) {
				valid_file_size = file.size < max_file_size;
			}

			if (!is_correct_type) {
				console.warn('File skipped because of invalid file type', file);
			}
			if (!valid_file_size) {
				console.warn('File skipped because of invalid file size', file.size, file);
			}

			return is_correct_type && valid_file_size;
		},
		upload_files() {
			if (this.show_file_browser) {
				return this.upload_via_file_browser();
			}
			if (this.show_web_link) {
				return this.upload_via_web_link();
			}
			if (this.as_dataurl) {
				return this.return_as_dataurl();
			}
			return frappe.run_serially(
				this.files.map(
					(file, i) =>
						() => this.upload_file(file, i)
				)
			);
		},
		upload_via_file_browser() {
			let selected_file = this.$refs.file_browser.selected_node;
			if (!selected_file.value) {
				frappe.msgprint(__('Click on a file to select it.'));
				return Promise.reject();
			}

			return this.upload_file({
				file_url: selected_file.file_url
			});
		},
		upload_via_web_link() {
			let file_url = this.$refs.web_link.url;
			if (!file_url) {
				frappe.msgprint(__('Invalid URL'));
				return Promise.reject();
			}

			return this.upload_file({
				file_url
			});
		},
		return_as_dataurl() {
			let promises = this.files.map(file =>
				frappe.dom.file_to_base64(file.file_obj)
					.then(dataurl => {
						file.dataurl = dataurl;
						this.on_success && this.on_success(file);
					})
			);
			return Promise.all(promises);
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
							let file_doc = null;
							try {
								r = JSON.parse(xhr.responseText);
								if (r.message.doctype === 'File') {
									file_doc = r.message;
								}
							} catch(e) {
								r = xhr.responseText;
							}

							file.doc = file_doc;

							if (this.on_success) {
								this.on_success(file_doc, r);
							}
						} else if (xhr.status === 403) {
							let response = JSON.parse(xhr.responseText);
							frappe.msgprint({
								title: __('Not permitted'),
								indicator: 'red',
								message: response._error_message
							});
						} else {
							file.failed = true;
							let error = null;
							try {
								error = JSON.parse(xhr.responseText);
							} catch(e) {
								// pass
							}
							frappe.request.cleanup({}, error);
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
