import path from "path"
import fs from "fs"

export function getCommonSiteConfig() {
	let currentDir = path.resolve(".")
	while (currentDir !== "/") {
		if (fs.existsSync(path.join(currentDir, "sites")) && fs.existsSync(path.join(currentDir, "apps"))) {
			const configPath = path.join(currentDir, "sites", "common_site_config.json")
			return fs.existsSync(configPath) ? JSON.parse(fs.readFileSync(configPath, "utf8")) : null
		}
		currentDir = path.resolve(currentDir, "..")
	}
	return null
}

export function getViteDevServerPort() {
	const commonSiteConfig = getCommonSiteConfig()
	const webserverPort = Number(process.env.FRAPPE_WEB_SERVER_PORT || commonSiteConfig?.webserver_port || 8000)
	return 8080 + (webserverPort - 8000)
}
