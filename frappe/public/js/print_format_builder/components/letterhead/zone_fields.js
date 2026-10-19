const HEADER = {
	source: "source",
	content: "content",
	image: "image",
	align: "align",
	height: "image_height",
	width: "image_width",
};
const FOOTER = {
	source: "footer_source",
	content: "footer",
	image: "footer_image",
	align: "footer_align",
	height: "footer_image_height",
	width: "footer_image_width",
};

export const zone_fields = (zone) => (zone === "header" ? HEADER : FOOTER);
