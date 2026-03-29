export interface ToDo {
  name: string
  description: string
  status: 'Open' | 'Closed' | 'Cancelled'
  priority: 'Low' | 'Medium' | 'High'
  date: string | null
  modified: string
  owner: string
}

declare global {
  interface Window {
    csrf_token: string
    site_name: string
    frappe_version: string
  }
}
