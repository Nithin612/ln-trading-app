/** Entry for the live-table browser benchmark (see LiveTableBench.tsx). */

import { createRoot } from 'react-dom/client'

import '@/styles/globals.css'
import { installBenchSocket } from './benchSocket'
import { LiveTableBench } from './LiveTableBench'

installBenchSocket()

const el = document.getElementById('root')
if (el) {
  // No StrictMode: its double-render would double every Profiler commit and
  // misreport the steady-state cost this benchmark exists to measure.
  createRoot(el).render(<LiveTableBench />)
}
