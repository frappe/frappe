import tsToJSON from "../utils/tsToJSON.mjs"

const configMap = {
	"frappe-ui": {
		typesFolder: "../node_modules/frappe-ui/src/components/types",
		destFolder: "src/json_types/frappeui",
		tsconfigPath: "../node_modules/frappe-ui/tsconfig.json",
	},
	studio: {
		typesFolder: "src/types/studio_components",
		destFolder: "src/json_types/studio",
		tsconfigPath: "tsconfig.json",
	},
}

const moduleName = process.argv[2]
if (!moduleName || !configMap[moduleName]) {
	console.error(
		`Invalid or missing moduleName. Please specify one of the following modules:\n- ${Object.keys(configMap).join("\n- ")}`,
	)
	process.exit(1)
}

const { typesFolder, destFolder, tsconfigPath } = configMap[moduleName]
tsToJSON(typesFolder, destFolder, tsconfigPath)
