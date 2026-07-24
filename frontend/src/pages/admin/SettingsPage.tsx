import { useThemeStore } from '@/store/themeStore'
import { useUiPrefsStore } from '@/store/uiPrefsStore'
import type { UiFont, NumFont } from '@/store/uiPrefsStore'
import type { Theme } from '@/store/themeStore'
import { PageHeader } from '@/components/layout/PageHeader'
import { Slider } from '@/components/ui/slider'

/* ── Theme card data ────────────────────────────────────────────────────── */
const THEMES: { id: Theme; label: string; desc: string; bg: string; accent: string }[] = [
  { id: 'midnight', label: 'Midnight', desc: 'Deep navy · cyan',    bg: '#0a0f1c', accent: '#06b6d4' },
  { id: 'carbon',   label: 'Carbon',   desc: 'Pure black · amber',  bg: '#000000', accent: '#f59e0b' },
  { id: 'ocean',    label: 'Ocean',    desc: 'Dark teal · mint',    bg: '#0c1c1f', accent: '#2dd4bf' },
  { id: 'daybreak', label: 'Daybreak', desc: 'Light · indigo',      bg: '#f8fafc', accent: '#4f46e5' },
]

/* ── Font options ───────────────────────────────────────────────────────── */
const UI_FONTS: { value: UiFont; label: string; desc: string }[] = [
  { value: 'inter',         label: 'Inter',         desc: 'Default, professional' },
  { value: 'geist',         label: 'Geist',         desc: 'Modern, geometric' },
  { value: 'ibm-plex-sans', label: 'IBM Plex Sans', desc: 'Institutional' },
  { value: 'roboto',        label: 'Roboto',        desc: 'Google neutral' },
]

const NUM_FONTS: { value: NumFont; label: string; desc: string }[] = [
  { value: 'jetbrains-mono', label: 'JetBrains Mono', desc: 'Sharp, dev-grade' },
  { value: 'ibm-plex-mono',  label: 'IBM Plex Mono',  desc: 'Pairs with IBM Plex' },
  { value: 'roboto-mono',    label: 'Roboto Mono',    desc: 'Pairs with Roboto' },
  { value: 'inter',          label: 'Inter (tabular)', desc: 'Unified look' },
]

/* ── Font size presets ─────────────────────────────────────────────────── */
const SIZE_PRESETS = [
  { label: 'Compact',     px: 13 },
  { label: 'Default',     px: 15 },
  { label: 'Comfortable', px: 17 },
  { label: 'Large',       px: 19 },
  { label: 'X-Large',     px: 21 },
]

function SettingSection({ title, description, children }: {
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <div className="card space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-(--color-text)">{title}</h3>
        <p className="text-xs text-(--color-text-muted) mt-0.5">{description}</p>
      </div>
      <div>{children}</div>
    </div>
  )
}

function FontRadio({ active, onClick, children }: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-2 rounded-md border text-sm text-left transition-colors w-full"
      style={{
        backgroundColor: active ? 'var(--color-accent-bg)' : 'var(--color-surface-3)',
        borderColor: active ? 'var(--color-accent)' : 'var(--color-border)',
        color: active ? 'var(--color-accent)' : 'var(--color-text-muted)',
      }}
    >
      <span
        className="w-3 h-3 rounded-full border-2 flex-shrink-0"
        style={{ borderColor: active ? 'var(--color-accent)' : 'var(--color-border)', background: active ? 'var(--color-accent)' : 'transparent' }}
      />
      {children}
    </button>
  )
}

export function SettingsPage() {
  const { theme, setTheme } = useThemeStore()
  const { fontSizePx, setFontSizePx, uiFont, setUiFont, numFont, setNumFont } = useUiPrefsStore()

  const uiFontFamily = UI_FONTS.find((f) => f.value === uiFont)?.label ?? 'Inter'
  const numFontFamily = NUM_FONTS.find((f) => f.value === numFont)?.label ?? 'JetBrains Mono'

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Appearance Settings" subtitle="Admin-only — applies to all sessions on this device" />

      {/* ── Color Theme ── */}
      <SettingSection
        title="Color Theme"
        description="Four finance-tuned themes. Each one is designed for a specific lighting context."
      >
        <div className="grid grid-cols-2 gap-3">
          {THEMES.map((t) => {
            const active = theme === t.id
            return (
              <button
                key={t.id}
                onClick={() => setTheme(t.id)}
                className="relative rounded-lg border-2 p-3 text-left transition-all"
                style={{
                  backgroundColor: t.bg,
                  borderColor: active ? t.accent : 'transparent',
                  outline: active ? `2px solid ${t.accent}` : 'none',
                  outlineOffset: '1px',
                  boxShadow: active ? `0 0 0 4px ${t.accent}28` : 'none',
                }}
              >
                {/* Accent swatch */}
                <div className="flex items-center gap-2 mb-2">
                  <div
                    className="w-6 h-6 rounded-full border border-white/20 flex-shrink-0"
                    style={{ backgroundColor: t.accent }}
                  />
                  <span
                    className="text-sm font-semibold"
                    style={{ color: t.id === 'daybreak' ? '#0f172a' : '#e2e8f0' }}
                  >
                    {t.label}
                  </span>
                </div>
                <p
                  className="text-xs"
                  style={{ color: t.id === 'daybreak' ? '#64748b' : '#94a3b8' }}
                >
                  {t.desc}
                </p>
                {active && (
                  <span
                    className="absolute top-2 right-2 text-[10px] font-bold px-1.5 py-0.5 rounded"
                    style={{ backgroundColor: t.accent, color: t.id === 'carbon' ? '#000' : '#fff' }}
                  >
                    ACTIVE
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </SettingSection>

      {/* ── Font Size ── */}
      <SettingSection
        title="Font Size"
        description="Drag the slider or pick a preset. Adjusts text density across all pages."
      >
        <div className="space-y-4">
          {/* Live preview */}
          <div
            className="rounded-lg border border-(--color-border) bg-(--color-surface-2) p-4 text-(--color-text-muted) transition-none"
            style={{ fontSize: `${fontSizePx}px` }}
          >
            Preview: RELIANCE INFY TCS — ₹2,345.50 +1.2% BUY signal
          </div>

          {/* Slider row */}
          <div className="flex items-center gap-3">
            <span className="text-(--color-text-muted) select-none" style={{ fontSize: 11 }}>A</span>
            <div className="flex-1">
              <Slider
                value={fontSizePx}
                onChange={setFontSizePx}
                min={12}
                max={22}
                step={1}
              />
            </div>
            <span className="text-base text-(--color-text) select-none" style={{ fontSize: 22 }}>A</span>
            <span className="w-10 text-right text-sm tabular-nums text-(--color-text-secondary)">
              {fontSizePx}px
            </span>
          </div>

          {/* Preset chips */}
          <div className="flex flex-wrap gap-2">
            {SIZE_PRESETS.map((p) => (
              <button
                key={p.label}
                onClick={() => setFontSizePx(p.px)}
                className="px-3 py-1 rounded-md border text-xs font-medium transition-colors"
                style={{
                  backgroundColor: fontSizePx === p.px ? 'var(--color-accent)' : 'var(--color-surface-3)',
                  borderColor: fontSizePx === p.px ? 'var(--color-accent)' : 'var(--color-border)',
                  color: fontSizePx === p.px ? 'var(--color-primary-foreground)' : 'var(--color-text-muted)',
                }}
              >
                {p.label}
                <span className="ml-1 opacity-60">{p.px}px</span>
              </button>
            ))}
          </div>
        </div>
      </SettingSection>

      {/* ── Fonts ── */}
      <SettingSection
        title="Font Family"
        description="Set UI text and numeric fonts independently for maximum readability."
      >
        <div className="grid grid-cols-2 gap-4">
          {/* UI font */}
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-(--color-text-secondary)">UI Font</p>
            {UI_FONTS.map((f) => (
              <FontRadio key={f.value} active={uiFont === f.value} onClick={() => setUiFont(f.value)}>
                <div>
                  <p className="text-sm font-medium leading-none">{f.label}</p>
                  <p className="text-xs opacity-60 mt-0.5">{f.desc}</p>
                </div>
              </FontRadio>
            ))}
          </div>

          {/* Numeric font */}
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-(--color-text-secondary)">Numeric Font</p>
            {NUM_FONTS.map((f) => (
              <FontRadio key={f.value} active={numFont === f.value} onClick={() => setNumFont(f.value)}>
                <div>
                  <p className="text-sm font-medium leading-none">{f.label}</p>
                  <p className="text-xs opacity-60 mt-0.5">{f.desc}</p>
                </div>
              </FontRadio>
            ))}
          </div>
        </div>

        {/* Font preview */}
        <div className="mt-4 rounded-lg border border-(--color-border) bg-(--color-surface-2) p-4 space-y-1">
          <p className="text-xs text-(--color-text-muted) mb-2">Preview</p>
          <p style={{ fontFamily: `var(--font-ui)` }} className="text-sm text-(--color-text)">
            UI font ({uiFontFamily}): Buy RELIANCE @ ₹2,345.50 BUY signal
          </p>
          <p style={{ fontFamily: `var(--font-num)` }} className="text-sm text-(--color-text-secondary) tabular-nums">
            Numbers ({numFontFamily}): ₹2,345.50 · +1.20% · Qty 100 · P&L +₹1,234.56
          </p>
        </div>
      </SettingSection>

      <p className="text-xs text-(--color-text-muted) text-center">
        Settings are stored in your browser and applied immediately. They persist across page reloads.
      </p>
    </div>
  )
}
