import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useThemeStore } from '@/store/themeStore'
import { useUiPrefsStore } from '@/store/uiPrefsStore'

describe('themeStore', () => {
  beforeEach(() => {
    useThemeStore.setState({ theme: 'slate' })
    localStorage.clear()
  })

  it('defaults to slate', () => {
    expect(useThemeStore.getState().theme).toBe('slate')
  })

  it('toggles from dark theme to daybreak', () => {
    useThemeStore.getState().toggle()
    expect(useThemeStore.getState().theme).toBe('daybreak')
  })

  it('toggles from daybreak to slate', () => {
    useThemeStore.setState({ theme: 'daybreak' })
    useThemeStore.getState().toggle()
    expect(useThemeStore.getState().theme).toBe('slate')
  })

  it('setTheme sets any valid theme', () => {
    useThemeStore.getState().setTheme('carbon')
    expect(useThemeStore.getState().theme).toBe('carbon')
    useThemeStore.getState().setTheme('ocean')
    expect(useThemeStore.getState().theme).toBe('ocean')
  })

  it('persists to localStorage on toggle', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem')
    useThemeStore.getState().toggle()
    expect(spy).toHaveBeenCalledWith('ui-theme', 'daybreak')
  })

  it('persists to localStorage on setTheme', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem')
    useThemeStore.getState().setTheme('carbon')
    expect(spy).toHaveBeenCalledWith('ui-theme', 'carbon')
  })
})

describe('uiPrefsStore', () => {
  beforeEach(() => {
    useUiPrefsStore.setState({ fontSize: 'md', fontFamily: 'inter', fontSizePx: 15, uiFont: 'inter', numFont: 'jetbrains-mono' })
    localStorage.clear()
  })

  it('defaults to md fontSize and inter fontFamily', () => {
    const { fontSize, fontFamily } = useUiPrefsStore.getState()
    expect(fontSize).toBe('md')
    expect(fontFamily).toBe('inter')
  })

  it('setFontSize updates fontSize', () => {
    useUiPrefsStore.getState().setFontSize('lg')
    expect(useUiPrefsStore.getState().fontSize).toBe('lg')
  })

  it('setFontFamily updates fontFamily', () => {
    useUiPrefsStore.getState().setFontFamily('geist')
    expect(useUiPrefsStore.getState().fontFamily).toBe('geist')
  })

  it('setFontSizePx updates fontSizePx', () => {
    useUiPrefsStore.getState().setFontSizePx(17)
    expect(useUiPrefsStore.getState().fontSizePx).toBe(17)
  })

  it('setUiFont updates uiFont', () => {
    useUiPrefsStore.getState().setUiFont('geist')
    expect(useUiPrefsStore.getState().uiFont).toBe('geist')
  })

  it('setNumFont updates numFont', () => {
    useUiPrefsStore.getState().setNumFont('ibm-plex-mono')
    expect(useUiPrefsStore.getState().numFont).toBe('ibm-plex-mono')
  })

  it('persists fontSize to localStorage', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem')
    useUiPrefsStore.getState().setFontSize('sm')
    expect(spy).toHaveBeenCalledWith('ui-font-size', 'sm')
  })

  it('persists fontFamily to localStorage', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem')
    useUiPrefsStore.getState().setFontFamily('system')
    expect(spy).toHaveBeenCalledWith('ui-font-family', 'system')
  })

  it('persists fontSizePx to localStorage', () => {
    const spy = vi.spyOn(Storage.prototype, 'setItem')
    useUiPrefsStore.getState().setFontSizePx(19)
    expect(spy).toHaveBeenCalledWith('ui-font-size-px', '19')
  })
})
