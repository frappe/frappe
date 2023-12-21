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
								: button.value === aspect_ratio,
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
<<<<<<< HEAD
export default {
	name: "ImageCropper",
	props: ["file", "fixed_aspect_ratio"],
	data() {
		let aspect_ratio = this.fixed_aspect_ratio != null ? this.fixed_aspect_ratio : NaN;
		return {
			src: null,
			cropper: null,
			image: null,
			aspect_ratio,
		};
=======

// props
const props = defineProps({
	file: Object,
	fixed_aspect_ratio: Number,
});

// emits
let emit = defineEmits(["toggle_image_cropper"]);

// variables
let aspect_ratio = ref(props.fixed_aspect_ratio != null ? props.fixed_aspect_ratio : NaN);
let src = ref(null);
let cropper = ref(null);
let image = ref(null);
let image_ref = ref(null); // Template ref

// methods
function crop_image() {
	props.file.crop_box_data = cropper.value.getData();
	const canvas = cropper.value.getCroppedCanvas();
	const file_type = props.file.file_obj.type;
	canvas.toBlob((blob) => {
		var cropped_file_obj = new File([blob], props.file.name, {
			type: blob.type,
		});
		props.file.file_obj = cropped_file_obj;
		emit("toggle_image_cropper");
	}, file_type);
}

// mounted
onMounted(() => {
	if (window.FileReader) {
		let fr = new FileReader();
		fr.onload = () => (src.value = fr.result);
		fr.readAsDataURL(props.file.cropper_file);
	}
	let crop_box = props.file.crop_box_data;
	image.value = image_ref.value;
	image.value.onload = () => {
		cropper.value = new Cropper(image.value, {
			zoomable: false,
			scalable: false,
			viewMode: 1,
			data: crop_box,
			aspectRatio: aspect_ratio.value,
		});
		window.cropper = cropper.value;
	};
});

//  computed
let aspect_ratio_buttons = computed(() => {
	return [
		{
			label: __("1:1", null, "Image Cropper"),
			value: 1,
		},
		{
			label: __("4:3", null, "Image Cropper"),
			value: 4 / 3,
		},
		{
			label: __("16:9", null, "Image Cropper"),
			value: 16 / 9,
		},
		{
			label: __("Free", null, "Image Cropper"),
			value: NaN,
		},
	];
});

// watcher
watch(
	aspect_ratio,
	(value) => {
		if (cropper.value) {
			cropper.value.setAspectRatio(value);
		}
>>>>>>> 1d23888475 (fix(translations): Add context to Image Cropper text (#23908))
	},
	watch: {
		aspect_ratio(value) {
			if (this.cropper) {
				this.cropper.setAspectRatio(value);
			}
		},
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
				aspectRatio: this.aspect_ratio,
			});
			window.cropper = this.cropper;
		};
	},
	computed: {
		aspect_ratio_buttons() {
			return [
				{
					label: __("1:1"),
					value: 1,
				},
				{
					label: __("4:3"),
					value: 4 / 3,
				},
				{
					label: __("16:9"),
					value: 16 / 9,
				},
				{
					label: __("Free"),
					value: NaN,
				},
			];
		},
	},
	methods: {
		crop_image() {
			this.file.crop_box_data = this.cropper.getData();
			const canvas = this.cropper.getCroppedCanvas();
			const file_type = this.file.file_obj.type;
			canvas.toBlob((blob) => {
				var cropped_file_obj = new File([blob], this.file.name, {
					type: blob.type,
				});
				this.file.file_obj = cropped_file_obj;
				this.$emit("toggle_image_cropper");
			}, file_type);
		},
	},
};
</script>

<style scoped>
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
