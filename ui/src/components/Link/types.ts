interface InputLabelingProps {
  label?: string
  description?: string
  error?: string | Error
  required?: boolean
}

export interface LinkProps extends InputLabelingProps {
  doctype: string
  filters?: Record<string, unknown>
  creatable?: boolean
  disabled?: boolean
  placeholder?: string
}

export interface LinkEmits {
  'update:modelValue': [value: string | null]
  'update:open': [value: boolean]
  create: [query: string]
}

export interface LinkExposed {
  reload: () => void
}

export type LinkOption = {
  label: string
  value: string
  description?: string
}
