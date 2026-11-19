// Draws nothing: hands a restored draft's attachments to a fresh editor once, through its `actions` slot.
import { defineComponent, onMounted, type PropType } from "vue";
import type { UploadedFile } from "@framework/ui/Composer";

export default defineComponent({
	name: "AttachmentSeed",
	props: {
		files: { type: Array as PropType<UploadedFile[]>, required: true },
		add: {
			type: Function as PropType<(file: UploadedFile) => void>,
			required: true,
		},
	},
	setup(props) {
		onMounted(() => props.files.forEach((file) => props.add(file)));
		return () => null;
	},
});
