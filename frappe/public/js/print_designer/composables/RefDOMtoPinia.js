import { ref } from "vue";
export function useRefDOMtoPinia() {
	const DOMElement = ref(null);
	const id = ref(null);

	const setReferance = (element) => (el) => {
		DOMElement.value = el;
		element.DOMRef = el;
		el.piniaElementRef = element;
		id.value = element.id;
	};

	return { id, DOMElement, setReferance };
}
