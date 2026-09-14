/// <reference types="node" />
// ⚠ File-scoped node types, deliberately not `types: ["node"]` in tsconfig.app.json —
// widening the whole app project so one test can read a file would let node globals leak
// into browser code. `@types/node` is already installed.
// ⛔ And NOT Vite's `?raw`: vitest disables CSS processing, so `import x from '…css?raw'`
// resolves to an EMPTY STRING. Measured — it silently yielded `len: 0`, which would have
// made every contrast assertion iterate an empty object and PASS. That is precisely the
// "guard test that cannot fail" shape, which is why the parse canary below exists and is
// what caught it.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Contrast regression test for the load-bearing token pairs.
 *
 * ⭐ WHY THIS EXISTS. `tokens.css` records contrast measurements in prose comments, and
 * that convention has now failed twice: daybreak's `--color-loss` shipped at 3.95:1 under
 * a comment, and `--color-loss` on the row surface shipped at 3.96:1 in SLATE — the
 * default theme — two weeks later. This repo already has the lesson written down: *"a
 * documented safety net is worth nothing without a test that fails when it lapses."*
 *
 * ⚠ The tightest margin in the file is daybreak's `--color-warning` on
 * `--color-warning-bg` at **4.51:1**, clearing AA by 0.01 — and two components now paint
 * that pair. A one-shade nudge to either value breaks AA silently, in the single theme
 * where it is closest. This test is what notices.
 *
 * ⛔ SCOPE, stated so it is not over-read: this checks only the pairs listed below, which
 * are the ones carrying safety or provenance copy. It does NOT prove the stylesheet is
 * accessible, and it cannot see a pair assembled at runtime in a component.
 */

const AA_NORMAL_TEXT = 4.5

const THEMES = ['slate', 'midnight', 'carbon', 'ocean', 'daybreak'] as const
type Theme = (typeof THEMES)[number]

/** foreground token, background token, why it must stay readable. */
const LOAD_BEARING: ReadonlyArray<readonly [string, string, string]> = [
  ['--color-warning', '--color-warning-bg', 'V2 price-provenance pill + V1 coverage alarm'],
  ['--color-text-secondary', '--color-surface-2', 'funnel rung labels; "last 1m close"'],
  ['--color-text', '--color-loss-bg', 'the stranded-position banner'],
  ['--color-text', '--color-surface-2', 'every table cell'],
  ['--color-loss', '--color-loss-bg', '⊘ Blocked, hit_sl / rejected / sell pills'],
  ['--color-bear', '--color-loss-bg', 'the SELL pill'],
  ['--color-loss', '--color-surface-2', 'every negative P&L figure'],
  ['--color-bear', '--color-surface-2', 'the SL column, ▼ glyphs'],
  ['--color-profit', '--color-profit-bg', 'tp_hit / buy pills'],
  ['--color-bull', '--color-profit-bg', 'the BUY pill'],
  ['--color-profit', '--color-surface-2', 'every positive P&L figure'],
  ['--color-bull', '--color-surface-2', '▲ glyphs'],
]

/**
 * ⛔ MEASURED DEBT — pairs below AA **today**, recorded rather than hidden or silently fixed.
 *
 * ⭐ WHY A RATCHET AND NOT A FIX: choosing a different red or green changes the appearance
 * of every P&L figure in the app across five themes. That is a design decision for the
 * owner, not a side effect of the change that happened to measure it. So this list is
 * asserted EXACTLY: a NEW failure fails the suite, and FIXING one also fails it — forcing
 * the list to shrink deliberately rather than drift.
 *
 * ⭐⭐ WHAT IT REVEALS: the 2026-09-02 review fixed daybreak `--color-loss` (3.95 → 5.30)
 * and left its siblings alone. `--color-bear` in daybreak still measures **3.95** — the
 * very number that triggered that fix — because the fix was applied to one TOKEN instead
 * of to the semantic GROUP. `--color-profit`/`--color-bull` on daybreak were never
 * measured at all. **A fix applied to one token of a semantic group is not a fix.**
 */
const KNOWN_BELOW_AA: ReadonlyArray<string> = [
  // Dark themes: loss/bear are red-500 (#ef4444). red-400 (#f87171) clears every one of
  // these — measured 5.84 on loss-bg, 5.38/5.68/6.66 on surface-2.
  'slate: --color-loss on --color-loss-bg = 4.29',
  'slate: --color-bear on --color-loss-bg = 4.29',
  'slate: --color-loss on --color-surface-2 = 3.96',
  'slate: --color-bear on --color-surface-2 = 3.96',
  'midnight: --color-loss on --color-loss-bg = 4.29',
  'midnight: --color-bear on --color-loss-bg = 4.29',
  'midnight: --color-loss on --color-surface-2 = 4.18',
  'midnight: --color-bear on --color-surface-2 = 4.18',
  'carbon: --color-loss on --color-loss-bg = 4.29',
  'carbon: --color-bear on --color-loss-bg = 4.29',
  // daybreak: the half-applied 2026-09-02 fix, plus a green nobody ever measured on light.
  'daybreak: --color-bear on --color-loss-bg = 3.95',
  'daybreak: --color-bear on --color-surface-2 = 4.41',
  'daybreak: --color-profit on --color-profit-bg = 3.32',
  'daybreak: --color-bull on --color-profit-bg = 3.32',
  'daybreak: --color-profit on --color-surface-2 = 3.44',
  'daybreak: --color-bull on --color-surface-2 = 3.44',
]

function parseThemes(css: string): Record<Theme, Record<string, string>> {
  // `:root, :root[data-theme="slate"] { … }` — one block can serve several selectors, and
  // midnight/daybreak each carry a `dark`/`light` alias. Bare `:root` is the base every
  // theme inherits, so it is applied first and then overridden.
  const base: Record<string, string> = {}
  const out = Object.fromEntries(THEMES.map((t) => [t, {}])) as Record<
    Theme,
    Record<string, string>
  >

  for (const block of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const selector = block[1]
    if (!selector.includes(':root')) continue
    const vars: Record<string, string> = {}
    for (const d of block[2].matchAll(/(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;/g)) {
      vars[d[1]] = d[2]
    }
    if (Object.keys(vars).length === 0) continue

    const named = THEMES.filter((t) => selector.includes(`data-theme="${t}"`))
    if (named.length > 0) {
      for (const t of named) Object.assign(out[t], vars)
    } else if (/:root\s*(,|\{|$)/.test(selector)) {
      Object.assign(base, vars)
    }
  }
  for (const t of THEMES) out[t] = { ...base, ...out[t] }
  return out
}

function relativeLuminance(hex: string): number {
  let h = hex.replace('#', '')
  if (h.length === 3) h = [...h].map((c) => c + c).join('')
  const channel = (v: number) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
  const [r, g, b] = [0, 2, 4].map((i) => channel(parseInt(h.slice(i, i + 2), 16) / 255))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(fg: string, bg: string): number {
  const [a, b] = [relativeLuminance(fg), relativeLuminance(bg)]
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

// `process.cwd()` is the frontend package root under vitest.
const CSS = readFileSync(resolve(process.cwd(), 'src/styles/tokens.css'), 'utf8')
const RESOLVED = parseThemes(CSS)

describe('token contrast', () => {
  it('parses every theme, so a failure below cannot be an empty-object false pass', () => {
    for (const theme of THEMES) {
      expect(Object.keys(RESOLVED[theme]).length, `${theme} resolved no tokens`).toBeGreaterThan(20)
    }
  })

  it('every load-bearing pair is above AA, or is on the recorded-debt list', () => {
    const failures: string[] = []
    for (const theme of THEMES) {
      const vars = RESOLVED[theme]
      for (const [fg, bg] of LOAD_BEARING) {
        const [f, b] = [vars[fg], vars[bg]]
        expect(f, `${fg} is undefined in ${theme}`).toBeDefined()
        expect(b, `${bg} is undefined in ${theme}`).toBeDefined()
        const ratio = contrast(f, b)
        if (ratio < AA_NORMAL_TEXT) {
          failures.push(`${theme}: ${fg} on ${bg} = ${ratio.toFixed(2)}`)
        }
      }
    }
    // Asserted EXACTLY, both directions. A NEW pair below AA fails here; so does FIXING
    // one without removing its line, which is what keeps the debt list honest.
    expect(failures.sort()).toEqual([...KNOWN_BELOW_AA].sort())
  })

  it('canary: the known-bad pair this suite was written for still measures as bad', () => {
    // ⭐ A contrast test that cannot fail is worth nothing (the repo's own "guard test that
    // cannot fail" lesson). `--color-text-muted` on `--color-surface-2` is the pair we just
    // moved OFF for meaningful copy, and it is genuinely below AA in four themes. If this
    // ever goes green, the parser has broken — not the palette.
    const failing = THEMES.filter(
      (t) => contrast(RESOLVED[t]['--color-text-muted'], RESOLVED[t]['--color-surface-2']) < AA_NORMAL_TEXT,
    )
    expect(failing).toEqual(['slate', 'midnight', 'carbon', 'daybreak'])
  })
})
