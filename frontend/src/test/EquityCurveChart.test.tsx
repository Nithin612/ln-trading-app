import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import { EquityCurveChart } from '@/features/strategy/EquityCurveChart'

// U11 — the benchmark legend is plain DOM text (the chart SVG itself is hard to assert in jsdom),
// so we verify the buy-and-hold overlay is announced when present and absent otherwise.
describe('EquityCurveChart benchmark overlay (U11)', () => {
  it('shows the benchmark legend + return alongside the strategy return', () => {
    render(
      <EquityCurveChart
        data={[100, 105, 110.25]}
        label="run"
        benchmark={[100, 110, 121]}
        benchmarkLabel="NIFTY50 buy & hold"
        benchmarkReturnPct={21}
      />,
    )
    expect(screen.getByText(/NIFTY50 buy & hold/)).toBeInTheDocument()
    expect(screen.getByText(/\+21\.00%/)).toBeInTheDocument()
    expect(screen.getByText('+10.25%')).toBeInTheDocument() // strategy return still shown
  })

  it('omits the benchmark legend when no benchmark is provided', () => {
    render(<EquityCurveChart data={[100, 105]} label="run" />)
    expect(screen.queryByText(/buy & hold/)).not.toBeInTheDocument()
    expect(screen.getByText('+5.00%')).toBeInTheDocument()
  })
})
