export function slug(text) {
	return text.toLowerCase().replace(/ /g, '_');
}