import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { SettingsPage } from '@/pages/admin/SettingsPage'
import { useThemeStore } from '@/store/themeStore'
import { useUiPrefsStore } from '@/store/uiPrefsStore'

function setup() {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>,
  )
}

describe('SettingsPage', () => {
  beforeEach(() => {
    useThemeStore.setState({ theme: 'midnight' })
    useUiPrefsStore.setState({
      fontSize: 'md',
      fontFamily: 'inter',
      fontSizePx: 15,
      uiFont: 'inter',
      numFont: 'jetbrains-mono',
    })
    vi.spyOn(document.documentElement, 'setAttribute').mockImplementation(() => {})
    vi.spyOn(document.documentElement.style, 'setProperty').mockImplementation(() => {})
  })

  it('renders page header', () => {
    setup()
    expect(screen.getByText('Appearance Settings')).toBeInTheDocument()
  })

  it('shows all five theme cards', () => {
    setup()
    expect(screen.getByText('Slate')).toBeInTheDocument()
    expect(screen.getByText('Midnight')).toBeInTheDocument()
    expect(screen.getByText('Carbon')).toBeInTheDocument()
    expect(screen.getByText('Ocean')).toBeInTheDocument()
    expect(screen.getByText('Daybreak')).toBeInTheDocument()
  })

  it('switches to slate theme on click', () => {
    setup()
    useThemeStore.setState({ theme: 'midnight' })
    fireEvent.click(screen.getByText('Slate'))
    expect(useThemeStore.getState().theme).toBe('slate')
  })

  it('switches to carbon theme on click', () => {
    setup()
    fireEvent.click(screen.getByText('Carbon'))
    expect(useThemeStore.getState().theme).toBe('carbon')
  })

  it('switches to daybreak theme on click', () => {
    setup()
    fireEvent.click(screen.getByText('Daybreak'))
    expect(useThemeStore.getState().theme).toBe('daybreak')
  })

  it('shows ACTIVE badge on current theme card', () => {
    setup()
    expect(screen.getByText('ACTIVE')).toBeInTheDocument()
  })

  it('shows font size preset chips', () => {
    setup()
    expect(screen.getAllByText(/Compact/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/Default/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/Comfortable/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/Large/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/X-Large/).length).toBeGreaterThanOrEqual(1)
  })

  it('clicking a preset updates fontSizePx', () => {
    setup()
    // Find and click the Comfortable preset (17px)
    const chips = screen.getAllByText(/Comfortable/)
    fireEvent.click(chips[0])
    expect(useUiPrefsStore.getState().fontSizePx).toBe(17)
  })

  it('shows UI font options', () => {
    setup()
    expect(screen.getByText('Inter')).toBeInTheDocument()
    expect(screen.getByText('Geist')).toBeInTheDocument()
    expect(screen.getByText('IBM Plex Sans')).toBeInTheDocument()
  })

  it('shows numeric font options', () => {
    setup()
    expect(screen.getByText('JetBrains Mono')).toBeInTheDocument()
    expect(screen.getByText('IBM Plex Mono')).toBeInTheDocument()
  })

  it('clicking a UI font updates uiFont store', () => {
    setup()
    fireEvent.click(screen.getByText('Geist'))
    expect(useUiPrefsStore.getState().uiFont).toBe('geist')
  })

  it('clicking a numeric font updates numFont store', () => {
    setup()
    fireEvent.click(screen.getByText('IBM Plex Mono'))
    expect(useUiPrefsStore.getState().numFont).toBe('ibm-plex-mono')
  })

  it('shows preview text in both sections', () => {
    setup()
    expect(screen.getAllByText(/Preview/).length).toBeGreaterThanOrEqual(1)
  })
})
