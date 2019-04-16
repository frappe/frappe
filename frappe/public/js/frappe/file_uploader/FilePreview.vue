<template>
	<div class="file-preview">
		<div class="file-icon border rounded">
			<img
				v-if="is_image"
				:src="src"
				:alt="file.name"
				style="object-fit: cover; height: 100%;"
			>
			<div class="flex align-center justify-center" style="height: 100%;" v-else>
				<i class="octicon octicon-file-text text-extra-muted" style="font-size: 5rem;"></i>
			</div>
		</div>
		<div class="file-info">
			<div class="text-medium flex justify-between">
				<span :title="file.name">
					<a :href="file.doc.file_url" v-if="file.doc" target="_blank">
						<i v-if="file.doc.is_private" class="fa fa-lock fa-fw text-warning"></i>
						<i v-else class="fa fa-unlock-alt fa-fw text-warning"></i>
						{{ file.name | file_name }}
					</a>
					<span v-else>
						<span class="cursor-pointer" @click="$emit('toggle_private')" :title="__('Toggle Public/Private')">
							<i v-if="file.private" class="fa fa-lock fa-fw text-warning"></i>
							<i v-else class="fa fa-unlock-alt fa-fw text-warning"></i>
						</span>
						{{ file.name | file_name }}
					</span>
				</span>
				<i v-if="uploaded" class="octicon octicon-check text-success" :title="__('Uploaded successfully')"></i>
				<i v-if="file.failed" class="octicon octicon-x text-danger" :title="__('Upload failed')"></i>
			</div>
			<div>
				<span class="text-small text-muted">
					{{ file.file_obj.size | file_size }}
				</span>
			</div>
		</div>
		<div class="file-remove" @click="$emit('remove')" v-if="!uploaded">
			<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-x"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
		</div>
	</div>
</template>

<script>
export default {
	name: 'FilePreview',
	props: ['file'],
	data() {
		return {
			src: null
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
			return frappe.utils.file_name_ellipsis(value, 9);
		}
	},
	computed: {
		uploaded() {
			return this.file.total && this.file.total === this.file.progress && !this.file.failed;
		},
		is_image() {
			return this.file.file_obj.type.startsWith('image');
		}
	}
}
</script>

<style lang="less">
@import "frappe/public/less/variables.less";

.file-preview {
	width: 25%;
	padding-right: 15px;
	padding-bottom: 15px;
	position: relative;
}

.file-icon {
	height: 10rem;
	overflow: hidden;
}

.file-info {
	margin-top: 5px;
}

.file-remove {
	position: absolute;
	top: -7px;
	right: 7px;
	background: @text-dark;
    color: white;
    padding: 3px;
    border-radius: 50%;
    display: flex;
	cursor: pointer;
}
</style>
