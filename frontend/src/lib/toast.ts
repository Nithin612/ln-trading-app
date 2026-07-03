let globalToast: {
  success: (m: string) => void
  error: (m: string) => void
  info: (m: string) => void
  warning: (m: string) => void
} | null = null

export function registerGlobalToast(t: typeof globalToast) {
  globalToast = t
}

export const toast = {
  success: (m: string) => globalToast?.success(m),
  error: (m: string) => globalToast?.error(m),
  info: (m: string) => globalToast?.info(m),
  warning: (m: string) => globalToast?.warning(m),
}
