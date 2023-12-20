<script setup>
import { ref, onMounted } from "vue";

const div = ref(null);

const props = defineProps({
	modelValue: Array,
	placeholder: String,
});

const emit = defineEmits(["update:modelValue"]);

onMounted(() => {
	if (!frappe?.ui?.Tags || !window.Awesomplete || !frappe?.app) {
		return; // Not in desk
	}

	const editor = new frappe.ui.Tags({
		parent: $(div.value),
		placeholder: props.placeholder,
		onTagAdd() {
			emit("update:modelValue", editor.tagsList);
			refresh("");
		},
		onTagRemove() {
			emit("update:modelValue", editor.tagsList);
			refresh("");
		},
	});

	/** @type {HTMLInputElement} */
	const input = editor.$input.get(0);

	const awesomplete = new Awesomplete(input, {
		minChars: 0,
		maxItems: 99,
		list: [],
		item(item) {
			const el = $("<li></li>").data("item.autocomplete", item).get(0);
			el.append(item.label);
			if (editor.tagsList.includes(item.value)) {
				el.innerHTML += " " + frappe.utils.icon("tick");
			}
			return el;
		},
	});
	const refresh = (txt) => {
		frappe.call({
			method: "frappe.desk.doctype.tag.tag.get_tags",
			args: {
				doctype: "File",
				txt: txt.toLowerCase(),
			},
			callback(r) {
				awesomplete.list = r.message;
			},
		});
	};
	input.addEventListener("awesomplete-selectcomplete", (e) => {
		console.log([...editor.tagsList], editor.tagsList.includes(e.text.value));
		if (editor.tagsList.includes(e.text.value)) {
			editor.removeTag(e.text.value);
			const formTagRows = editor.$ul[0].querySelectorAll(".form-tag-row");
			console.log(formTagRows);
			formTagRows.forEach((el) => {
				if (el.textContent.trim() === e.text.label.trim()) {
					el.remove();
				}
			});
		} else {
			editor.addTag(e.text.value);
		}
		input.value = "";
		awesomplete.evaluate();
	});
	input.addEventListener("input", (e) => {
		refresh(e.target.value);
	});
	input.addEventListener("focus", () => {
		refresh(input.value);
	});

	const btn = editor.$placeholder.get(0);
	btn.id = "";
	btn.classList.remove("btn-reset");
	btn.classList.add("btn", "btn-default", "btn-xs");
});
</script>

<template>
	<ul ref="div" class="list-unstyled">
		<div class="form-sidebar-items"></div>
	</ul>
</template>

<style scoped>
.form-sidebar-items {
	margin-bottom: 4px;
}
</style>
