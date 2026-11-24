import { stringifyQuery, type LocationQuery } from "vue-router"

export type IslandRoute = {
	route?: string[]
	query?: LocationQuery
}

export function islandPath({ route = [], query = {} }: IslandRoute): string {
	const search = stringifyQuery(query)
	return `/${route.map(encodeURIComponent).join("/")}${search ? `?${search}` : ""}`
}
