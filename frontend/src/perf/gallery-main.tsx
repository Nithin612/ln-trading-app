/** Entry for the theme gallery (see ThemeGallery.tsx). */

import { createRoot } from 'react-dom/client'

import '@/styles/globals.css'
import { ThemeGallery } from './ThemeGallery'

const el = document.getElementById('root')
if (el) createRoot(el).render(<ThemeGallery />)
