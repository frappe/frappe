const URL_ATTRIBUTES = [
	"background",
	"cite",
	"href",
	"itemtype",
	"longdesc",
	"poster",
	"src",
	"xlink:href",
];
const SAFE_URL = /^(?:(?:https?|mailto|ftp|tel|file|sms):|[^#&/:?]*(?:[#/?]|$))/i;
const SAFE_DATA_URL =
	/^data:(?:image\/(?:bmp|gif|jpeg|jpg|png|tiff|webp)|video\/(?:mpeg|mp4|ogg|webm)|audio\/(?:mp3|oga|ogg|opus));base64,[\d+/a-z]+=*$/i;

export const ALLOWED_TAGS = {
	"*": ["class", "dir", "id", "lang", "role", /^aria-[\w-]*$/i],
	a: ["target", "href", "title", "rel"],
	img: ["src", "srcset", "alt", "title", "width", "height"],
	...Object.fromEntries(
		"area b br col code div em hr h1 h2 h3 h4 h5 h6 i li ol p pre s small span sub sup strong u ul"
			.split(" ")
			.map((tag) => [tag, []])
	),
};

function is_allowed(attribute, allowed) {
	const name = attribute.nodeName.toLowerCase();
	if (allowed.includes(name)) {
		return URL_ATTRIBUTES.includes(name)
			? SAFE_URL.test(attribute.nodeValue) || SAFE_DATA_URL.test(attribute.nodeValue)
			: true;
	}
	return allowed.some((rule) => rule instanceof RegExp && rule.test(name));
}

export function sanitize_html(html, allowed_tags = ALLOWED_TAGS, sanitize_fn = null) {
	if (!html.length) return html;
	if (typeof sanitize_fn === "function") return sanitize_fn(html);

	const doc = new DOMParser().parseFromString(html, "text/html");
	for (const element of doc.body.querySelectorAll("*")) {
		const tag = element.nodeName.toLowerCase();
		if (!Object.hasOwn(allowed_tags, tag)) {
			element.remove();
			continue;
		}
		const allowed = [...(allowed_tags["*"] || []), ...(allowed_tags[tag] || [])];
		for (const attribute of [...element.attributes]) {
			if (!is_allowed(attribute, allowed)) element.removeAttribute(attribute.nodeName);
		}
	}
	return doc.body.innerHTML;
}
