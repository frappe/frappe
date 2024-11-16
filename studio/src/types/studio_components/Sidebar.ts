export interface MenuItem {
	label: string
	route_to?: string
	selected?: boolean
	featherIcon?: string
}

export interface SidebarProps {
	title: string,
	logoSVG?: SVGElement,
	menuItems: MenuItem[]
}