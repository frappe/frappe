<template>
	<div>
		<div>
			<img ref="image" :src="src" :alt="file.name"/>
		</div>
		<br/>
		<div class="image-cropper-actions">
			<button class="btn btn-sm margin-right" v-if="!attach_doc_image" @click="$emit('toggle_image_cropper')">Back</button>
			<button class="btn btn-primary btn-sm margin-right" @click="crop_image" v-html="crop_button_text"></button>
		</div>
	</div>
</template>

<script>
import Cropper from "cropperjs";
export default {
	name: "ImageCropper",
	props: ["file", "attach_doc_image"],
	data() {
		return {
			src: null,
			cropper: null,
			image: null
		};
	},
	mounted() {
		if (window.FileReader) {
			let fr = new FileReader();
			fr.onload = () => (this.src = fr.result);
			fr.readAsDataURL(this.file.cropper_file);
		}
		aspect_ratio = this.attach_doc_image ? 1 : NaN;
		crop_box = this.file.crop_box_data;
		this.image = this.$refs.image;
		this.image.onload = () => {
			this.cropper = new Cropper(this.image, {
				zoomable: false,
				scalable: false,
				viewMode: 1,
				data: crop_box,
				aspectRatio: aspect_ratio
			});
		};
	},
	computed: {
		crop_button_text() {
			return this.attach_doc_image ? "Upload" : "Crop";
		}
	},
	methods: {
		crop_image() {
			this.file.crop_box_data = this.cropper.getData();
			const canvas = this.cropper.getCroppedCanvas();
			const file_type = this.file.file_obj.type;
			canvas.toBlob(blob => {
				var cropped_file_obj = new File([blob], this.file.name, {
					type: blob.type
				});
				this.file.file_obj = cropped_file_obj;
				this.$emit("toggle_image_cropper");
				if(this.attach_doc_image) {
					this.$emit("upload_after_crop");
				}
			}, file_type);
		}
	}
};
</script>
<style>
img {
	display: block;
	max-width: 100%;
	max-height: 600px;
}

.image-cropper-actions {
	display: flex;
	justify-content: flex-end;
}
</style>
