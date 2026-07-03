import { useContext } from 'react'
import { ToastContext, type ToastContextValue } from '@/lib/toast-context'

const noop = () => {}
const noopToast: ToastContextValue = { success: noop, error: noop, info: noop, warning: noop }

export function useToast(): ToastContextValue {
  return useContext(ToastContext) ?? noopToast
}
