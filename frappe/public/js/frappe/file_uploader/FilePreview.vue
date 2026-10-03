<template>
	<div class="file-preview-outline">
		<div class="file-preview">
			<div class="file-icon">
				<img v-if="is_image" :src="src" :alt="file.name" />
				<div class="fallback" v-else v-html="frappe.utils.icon('file', 'md')"></div>
			</div>
			<div>
				<div>
					<a class="flex" :href="file.doc.file_url" v-if="file.doc" target="_blank">
						<span class="file-name">{{ file.name }}</span>
					</a>
					<div class="flex align-center" v-else-if="allow_rename">
						<input
							ref="rename_input"
							type="text"
							class="form-control rename-input"
							v-model="edited_name"
							:title="__('File name (editable)')"
							@keydown.enter.prevent="submit_upload"
							@blur="commit_rename"
						/>
						<span class="file-extension" v-if="file_extension">{{
							file_extension
						}}</span>
					</div>
					<span class="file-name" v-else>{{ file.name }}</span>
				</div>

				<div>
					<span class="file-size">
						{{ file_size }}
					</span>
				</div>

				<div class="flex config-area">
					<label
						v-if="allow_toggle_optimize"
						class="frappe-checkbox"
						id="uploader-optimize-checkbox"
						><input
							type="checkbox"
							:checked="optimize"
							@change="emit('toggle_optimize')"
						/>{{ __("Optimize") }}</label
					>
					<label
						v-if="show_private_checkbox"
						class="frappe-checkbox"
						id="uploader-private-checkbox"
						><input
							type="checkbox"
							:checked="file.private"
							:disabled="!allow_toggle_private"
							@change="emit('toggle_private')"
						/>{{ __("Private") }}</label
					>
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
				<div v-if="uploaded" v-html="frappe.utils.icon('circle-check', 'lg')"></div>
				<div v-if="file.failed" v-html="frappe.utils.icon('circle-x', 'lg')"></div>
				<div class="file-action-buttons">
					<button
						v-if="is_cropable"
						class="btn btn-crop muted"
						@click="emit('toggle_image_cropper')"
						v-html="frappe.utils.icon('crop', 'md')"
						:title="__('Crop')"
					></button>
					<button
						v-if="!uploaded && !file.uploading && !file.failed"
						class="btn muted"
						@click="emit('remove')"
						v-html="frappe.utils.icon('x', 'md')"
						:title="__('Remove')"
					></button>
				</div>
			</div>
		</div>
		<div style="width: 100%">
			<div v-if="file.error_message" class="alert alert-danger mb-0 mt-2" role="alert">
				{{ file.error_message }}
			</div>
			<div
				v-if="!file.private && !file.error_message && !uploaded && !file.failed"
				class="alert alert-warning mb-0"
				role="alert"
			>
				{{
					__(
						"This file is public and can be accessed by anyone, even without logging in. Mark it private to limit access."
					)
				}}
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from "vue";
import ProgressRing from "./ProgressRing.vue";

// emits
let emit = defineEmits([
	"toggle_optimize",
	"toggle_private",
	"toggle_image_cropper",
	"remove",
	"rename",
	"upload",
]);

// props
const props = defineProps({
	file: Object,
	allow_toggle_private: {
		default: true,
	},
	show_private_checkbox: {
		default: true,
	},
	allow_toggle_optimize: {
		default: true,
	},
});

// variables
let src = ref(null);
let optimize = ref(props.file.optimize);
let rename_input = ref(null);
function split_extension(name) {
	const i = name ? name.lastIndexOf(".") : -1;
	return i > 0 ? [name.slice(0, i), name.slice(i)] : [name || "", ""];
}
let edited_name = ref(split_extension(props.file.name)[0]);
watch(
	() => props.file.name,
	(val) => (edited_name.value = split_extension(val)[0])
);

// computed
let file_size = computed(() => {
	return frappe.form.formatters.FileSize(props.file.file_obj.size);
});
let is_private = computed(() => {
	return props.file.doc ? props.file.doc.is_private : props.file.private;
});
let uploaded = computed(() => {
	return props.file.request_succeeded;
});
let is_image = computed(() => {
	return props.file.file_obj.type.startsWith("image");
});
let allow_toggle_optimize = computed(() => {
	let is_svg = props.file.file_obj.type == "image/svg+xml";
	return (
		props.allow_toggle_optimize &&
		is_image.value &&
		!is_svg &&
		!uploaded.value &&
		!props.file.failed
	);
});

let show_private_checkbox = computed(() => {
	return !uploaded.value && !props.file.failed;
});

let is_cropable = computed(() => {
	let croppable_types = ["image/jpeg", "image/png"];
	return (
		!uploaded.value &&
		!props.file.uploading &&
		!props.file.failed &&
		croppable_types.includes(props.file.file_obj.type)
	);
});
let progress = computed(() => {
	let value = Math.round((props.file.progress * 100) / props.file.total);
	if (isNaN(value)) {
		value = 0;
	}
	return value;
});
let allow_rename = computed(() => {
	return !props.file.doc && !uploaded.value && !props.file.uploading && !props.file.failed;
});
let file_extension = computed(() => split_extension(props.file.name)[1]);

// methods
function commit_rename() {
	let name = (edited_name.value || "").trim();
	if (name && name !== split_extension(props.file.name)[0]) {
		emit("rename", name);
	} else {
		edited_name.value = split_extension(props.file.name)[0];
	}
}
function submit_upload() {
	commit_rename();
	emit("upload");
}

// mounted
onMounted(() => {
	if (is_image.value) {
		if (window.FileReader) {
			let fr = new FileReader();
			fr.onload = () => (src.value = fr.result);
			fr.readAsDataURL(props.file.file_obj);
		}
	}
	// Fokus + Vorauswahl: direkt lostippen ersetzt den Namen, Enter lädt hoch.
	if (allow_rename.value) {
		nextTick(() => {
			rename_input.value?.focus();
			rename_input.value?.select();
		});
	}
});
</script>

<style scoped>
.file-preview-outline {
	padding: 0.75rem;
	border: 1px solid transparent;
	display: flex;
	flex-direction: column;
}

.file-preview {
	display: flex;
	align-items: center;
	flex-direction: row;
}

.file-preview-outline + .file-preview-outline {
	border-top-color: var(--border-color);
}

.file-preview-outline:hover {
	background-color: var(--bg-color);
	border-color: var(--dark-border-color);
	border-radius: var(--radius);
}

.file-preview-outline:hover + .file-preview-outline {
	border-top-color: transparent;
}

.file-icon {
	border-radius: var(--radius);
	width: 2.625rem;
	height: 2.625rem;
	overflow: hidden;
	margin-inline-end: var(--margin-md);
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
	border-radius: var(--radius);
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

.rename-input {
	font-size: var(--text-base);
	font-weight: var(--text-bold);
	color: var(--text-color);
	height: 26px;
	max-width: 280px;
	padding: 0 var(--padding-xs);
}

.file-extension {
	font-size: var(--text-base);
	font-weight: var(--text-bold);
	color: var(--text-muted);
	margin-left: var(--margin-xs);
}

.file-size {
	font-size: var(--text-sm);
	color: var(--text-light);
}

.file-actions {
	width: 3rem;
	flex-shrink: 0;
	margin-inline-start: auto;
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
</style>
