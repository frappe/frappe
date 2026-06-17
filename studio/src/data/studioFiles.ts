import { call } from "frappe-ui"

// A node in the editable file tree under an exported app's studio/<app>/ folder.
export interface StudioFileNode {
	label: string
	path: string
	is_folder: boolean
	children: StudioFileNode[]
}

interface StudioFileLocation {
	frappe_app: string
	studio_app: string
}

export function listStudioFiles(location: StudioFileLocation): Promise<StudioFileNode[]> {
	return call("studio.api.list_studio_files", { ...location })
}

export function readStudioFile(
	location: StudioFileLocation,
	file_path: string,
): Promise<{ path: string; content: string; hash: string }> {
	return call("studio.api.read_studio_file", { ...location, file_path })
}

export function writeStudioFile(
	location: StudioFileLocation,
	file_path: string,
	content: string,
	known_hash?: string,
): Promise<{ path: string; hash: string }> {
	return call("studio.api.write_studio_file", { ...location, file_path, content, known_hash })
}

export function createStudioFile(
	location: StudioFileLocation,
	file_path: string,
): Promise<{ path: string; hash: string }> {
	return call("studio.api.create_studio_file", { ...location, file_path })
}

export function createStudioFolder(
	location: StudioFileLocation,
	folder_path: string,
): Promise<{ path: string }> {
	return call("studio.api.create_studio_folder", { ...location, folder_path })
}

export function renameStudioFile(
	location: StudioFileLocation,
	file_path: string,
	new_path: string,
): Promise<{ path: string }> {
	return call("studio.api.rename_studio_file", { ...location, file_path, new_path })
}

export function deleteStudioFile(location: StudioFileLocation, file_path: string): Promise<void> {
	return call("studio.api.delete_studio_file", { ...location, file_path })
}

// Map a file extension to the language mode the Code editor understands.
export function languageForFile(path: string): "json" | "javascript" | "html" | "css" | "vue" {
	const extension = path.slice(path.lastIndexOf(".")).toLowerCase()
	if (extension === ".json") return "json"
	if (extension === ".css") return "css"
	if (extension === ".vue") return "vue"
	return "javascript"
}
