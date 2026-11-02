import path from "node:path"
import { fileURLToPath } from "node:url"
import baseConfig from "./tailwind.config.js"
import { findStudioAppFolders, mergeStudioAppConfigs } from "./tailwind/studioAppConfigs.js"

const appsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../")

// The editor renders every studio app, so it includes all their tailwind additions
export default mergeStudioAppConfigs(baseConfig, findStudioAppFolders(appsDir))
