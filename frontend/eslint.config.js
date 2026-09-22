// Keeps the desk on REST API v2: no v1 address and no frappe-ui fetch primitive in
// `frontend/src` or `ui/src`; every request goes through the wrapper in `ui/src/api`.
import tsParser from "@typescript-eslint/parser";
import vue from "eslint-plugin-vue";
import vueParser from "vue-eslint-parser";

// A literal that starts with one of these is a v1 address.
const V1_ADDRESS = "/^\\/api\\/(method|resource|v1)(\\/|$)/";

// frappe-ui's fetch layer. The wrapper never imports these either; it calls `fetch`.
const FRAPPE_UI_FETCH = [
	"call",
	"frappeRequest",
	"frappeRequest",
	"createResource",
	"createListResource",
	"createDocumentResource",
	"useCall",
	"useList",
	"useDoc",
	"useNewDoc",
	"useDoctype",
];

const v1AddressMessage =
	"A v1 address. Send the request through the wrapper in ui/src/api instead.";

const noV1Address = [
	"error",
	{ selector: `Literal[value=${V1_ADDRESS}]`, message: v1AddressMessage },
	{ selector: `TemplateElement[value.raw=${V1_ADDRESS}]`, message: v1AddressMessage },
];

const noFrappeUiFetch = [
	"error",
	{
		paths: [
			{
				name: "frappe-ui",
				importNames: FRAPPE_UI_FETCH,
				message: "frappe-ui's fetch layer sends to v1. Import from ui/src/api instead.",
			},
		],
		patterns: [
			{
				group: ["frappe-ui/src/*"],
				message:
					"frappe-ui's internals are not a public path. Import from ui/src/api instead.",
			},
		],
	},
];

// The core rule sees the script alone; the plugin's twin walks the template, where a
// plain attribute value is a `VLiteral`.
const noV1AddressInTemplate = [
	...noV1Address,
	{ selector: `VLiteral[value=${V1_ADDRESS}]`, message: v1AddressMessage },
];

const rules = {
	"no-restricted-syntax": noV1Address,
	"no-restricted-imports": noFrappeUiFetch,
	"vue/no-restricted-syntax": noV1AddressInTemplate,
};

const languageOptions = {
	ecmaVersion: "latest",
	sourceType: "module",
	parser: vueParser,
	parserOptions: { parser: tsParser, extraFileExtensions: [".vue"] },
};

export default [
	{
		// `ui/` is a sibling of `frontend/`, and eslint ignores a file above its working
		// directory, so the `lint` script runs from the repository root.
		files: ["frontend/src/**/*.{js,ts,vue}", "ui/src/**/*.{js,ts,vue}"],
		plugins: { vue },
		languageOptions,
		rules,
	},
];
