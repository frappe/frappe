<template>
	<div>
		<div>
			<img ref="image" :src="src" :alt="file.name" />
		</div>
		<div class="image-cropper-actions">
			<div>
				<div class="btn-group" v-if="fixed_aspect_ratio == null">
					<button
						v-for="button in aspect_ratio_buttons"
						type="button"
						class="btn btn-default btn-sm"
						:class="{
							active: isNaN(aspect_ratio)
								? isNaN(button.value)
								: button.value === aspect_ratio
						}"
						:key="button.label"
						@click="aspect_ratio = button.value"
					>
						{{ button.label }}
					</button>
				</div>
			</div>
			<div>
				<button
					class="btn btn-sm margin-right"
					@click="$emit('toggle_image_cropper')"
					v-if="fixed_aspect_ratio == null"
				>
					{{ __("Back") }}
				</button>
				<button class="btn btn-primary btn-sm" @click="crop_image">
					{{ __("Crop") }}
				</button>
			</div>
		</div>
	</div>
</template>

<script>
import Cropper from "cropperjs";
export default {
	name: "ImageCropper",
	props: ["file", "fixed_aspect_ratio"],
	data() {
		let aspect_ratio =
			this.fixed_aspect_ratio != null ? this.fixed_aspect_ratio : NaN;
		return {
			src: null,
			cropper: null,
			image: null,
			aspect_ratio
		};
	},
	watch: {
		aspect_ratio(value) {
			if (this.cropper) {
				this.cropper.setAspectRatio(value);
			}
		}
	},
	mounted() {
		if (window.FileReader) {
			let fr = new FileReader();
			fr.onload = () => (this.src = fr.result);
			fr.readAsDataURL(this.file.cropper_file);
		}
		let crop_box = this.file.crop_box_data;
		this.image = this.$refs.image;
		this.image.onload = () => {
			this.cropper = new Cropper(this.image, {
				zoomable: false,
				scalable: false,
				viewMode: 1,
				data: crop_box,
				aspectRatio: this.aspect_ratio
			});
			window.cropper = this.cropper;
		};
	},
	computed: {
		aspect_ratio_buttons() {
			return [
				{
					label: __("1:1"),
					value: 1
				},
				{
					label: __("4:3"),
					value: 4 / 3
				},
				{
					label: __("16:9"),
					value: 16 / 9
				},
				{
					label: __("Free"),
					value: NaN
				}
			];
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
	align-items: center;
	justify-content: space-between;
	margin-top: var(--margin-md);
}
</style>
