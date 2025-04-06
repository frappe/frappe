export interface MenuItem {
	label: string
	route_to?: string
	featherIcon?: string
}

export interface SidebarProps {
	title: string,
	logoSVG?: SVGElement,
	menuItems: MenuItem[]
}