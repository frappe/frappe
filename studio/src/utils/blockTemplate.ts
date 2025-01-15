import { BlockOptions } from "@/types";

function getBlockTemplate(
	type:
		| "body"
		| "fallback-component"
		| "placeholder-component"
): BlockOptions {
	switch (type) {
		case "body":
			return {
				componentId: "root",
				componentName: "div",
				originalElement: "body",
				children: [],
				baseStyles: {
					display: "flex",
					flexWrap: "wrap",
					flexDirection: "column",
					flexShrink: 0,
					alignItems: "center",
					width: "inherit",
					overflowX: "hidden",
				}
			};

		case "fallback-component":
			return {
				componentName: "p",
				originalElement: "__raw_html__",
				innerHTML: `<div style="color: red;background: #f4f4f4;display:flex;flex-direction:column;position:static;top:auto;left:auto;width: 600px;height: 275px;align-items:center;font-size: 30px;justify-content:center"><p>Component missing</p></div>`,
				baseStyles: {
					height: "fit-content",
					width: "fit-content",
				}
			}

		case "placeholder-component":
			return {
				componentName: "div",
				originalElement: "__raw_html__",
				innerHTML: `<div class="p-2 border-dashed border border-green-500 w-fit h-fit text-sm text-gray-700">Drop component here</div>`,
			}
	}
}

export default getBlockTemplate;