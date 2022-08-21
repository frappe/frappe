<template>
	<div class="file-preview">
		<div class="file-icon">
			<img
				v-if="is_image"
				:src="src"
				:alt="file.name"
			>
			<div class="fallback" v-else v-html="frappe.utils.icon('file', 'md')">
			</div>
		</div>
		<div>
			<div>
				<a class="flex" :href="file.doc.file_url" v-if="file.doc" target="_blank">
					<span class="file-name">{{ file.name | file_name }}</span>
				</a>
				<span class="file-name" v-else>{{ file.name | file_name }}</span>
			</div>

			<div>
				<span class="file-size">
					{{ file.file_obj.size | file_size }}
				</span>
			</div>

			<div class="flex config-area">
				<label v-if="is_optimizable" class="frappe-checkbox"><input type="checkbox" :checked="optimize" @change="$emit('toggle_optimize')">Optimize</label>
				<label class="frappe-checkbox"><input type="checkbox" :checked="file.private" @change="$emit('toggle_private')">Private</label>
			</div>
			<div>
				<span v-if="file.error_message" class="file-error text-danger">
					{{ file.error_message }}
				</span>
			</div>
		</div>
		<div class="file-actions">
			<ProgressRing
				v-show="file.uploading && !uploaded && !file.failed"
				primary="var(--primary-color)"
				secondary="var(--gray-200)"
				:radius="24"
				:progress="progress"
				:stroke="3"
			/>
			<div v-if="uploaded" v-html="frappe.utils.icon('solid-success', 'lg')"></div>
			<div v-if="file.failed" v-html="frappe.utils.icon('solid-error', 'lg')"></div>
			<div class="file-action-buttons">
				<button v-if="is_cropable" class="btn btn-crop muted" @click="$emit('toggle_image_cropper')" v-html="frappe.utils.icon('crop', 'md')"></button>
				<button v-if="!uploaded && !file.uploading && !file.failed" class="btn muted" @click="$emit('remove')" v-html="frappe.utils.icon('delete', 'md')"></button>
			</div>
		</div>
	</div>
</template>

<script>
import ProgressRing from './ProgressRing.vue';
export default {
	name: 'FilePreview',
	props: ['file'],
	components: {
		ProgressRing
	},
	data() {
		return {
			src: null,
			optimize: this.file.optimize
		}
	},
	mounted() {
		if (this.is_image) {
			if (window.FileReader) {
				let fr = new FileReader();
				fr.onload = () => this.src = fr.result;
				fr.readAsDataURL(this.file.file_obj);
			}
		}
	},
	filters: {
		file_size(value) {
			return frappe.form.formatters.FileSize(value);
		},
		file_name(value) {
			return value;
			// return frappe.utils.file_name_ellipsis(value, 9);
		}
	},
	computed: {
		is_private() {
			return this.file.doc ? this.file.doc.is_private : this.file.private;
		},
		uploaded() {
			return this.file.request_succeeded;
		},
		is_image() {
			return this.file.file_obj.type.startsWith('image');
		},
		is_optimizable() {
			let is_svg = this.file.file_obj.type == 'image/svg+xml';
			return this.is_image && !is_svg && !this.uploaded && !this.file.failed;
		},
		is_cropable() {
			let croppable_types = ['image/jpeg', 'image/png'];
			return !this.uploaded && !this.file.uploading && !this.file.failed && croppable_types.includes(this.file.file_obj.type);
		},
		progress() {
			let value = Math.round((this.file.progress * 100) / this.file.total);
			if (isNaN(value)) {
				value = 0;
			}
			return value;
		}
	}
}
</script>

<style>
.file-preview {
	display: flex;
	align-items: center;
	padding: 0.75rem;
	border: 1px solid transparent;
}

.file-preview + .file-preview {
	border-top-color: var(--border-color);
}

.file-preview:hover {
	background-color: var(--bg-color);
	border-color: var(--dark-border-color);
	border-radius: var(--border-radius);
}

.file-preview:hover + .file-preview {
	border-top-color: transparent;
}

.file-icon {
	border-radius: var(--border-radius);
	width: 2.625rem;
	height: 2.625rem;
	overflow: hidden;
	margin-right: var(--margin-md);
	flex-shrink: 0;
}

.file-icon img {
	width: 100%;
	height: 100%;
	object-fit: cover;
}

.file-icon .fallback {
	width: 100%;
	height: 100%;
	display: flex;
	align-items: center;
	justify-content: center;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
}

.file-name {
	font-size: var(--text-base);
	font-weight: var(--text-bold);
	color: var(--text-color);
	display: -webkit-box;
	-webkit-line-clamp: 1;
	-webkit-box-orient: vertical;
	overflow: hidden;
}

.file-size {
	font-size: var(--text-sm);
	color: var(--text-light);
}

.file-actions {
	width: 3rem;
	flex-shrink: 0;
	margin-left: auto;
	text-align: center;
}

.file-actions .btn {
	padding: var(--padding-xs);
	box-shadow: none;
}

.file-action-buttons {
	display: flex;
	justify-content: flex-end;
}

.muted {
	opacity: 0.5;
	transition: 0.3s;
}

.muted:hover {
	opacity: 1;
}

.frappe-checkbox {
	font-size: var(--text-sm);
	color: var(--text-light);
	display: flex;
	align-items: center;
	padding-top: 0.25rem;
}

.config-area {
	gap: 0.5rem;
}

.file-error {
	font-size: var(--text-sm);
	font-weight: var(--text-bold);
}
</style>
