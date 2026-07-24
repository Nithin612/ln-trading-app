import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { PriceCell } from '@/components/ui/PriceCell'

describe('PriceCell', () => {
  it('shows an em-dash when the value is undefined', () => {
    render(<PriceCell value={undefined} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('applies the formatter', () => {
    render(<PriceCell value={1234.5} format={(n) => `₹${n.toFixed(2)}`} />)
    expect(screen.getByText('₹1234.50')).toBeInTheDocument()
  })

  it('does not flash on first render', () => {
    render(<PriceCell value={100} />)
    const el = screen.getByText('100')
    expect(el.className).not.toContain('color-profit-bg')
    expect(el.className).not.toContain('color-loss-bg')
  })

  it('flashes up (profit tokens) when the value rises', async () => {
    const { rerender } = render(<PriceCell value={100} />)
    rerender(<PriceCell value={101} />)
    await waitFor(() => expect(screen.getByText('101').className).toContain('color-profit-bg'))
  })

  it('flashes down (loss tokens) when the value falls — never green on a down-tick', async () => {
    const { rerender } = render(<PriceCell value={100} />)
    rerender(<PriceCell value={99} />)
    await waitFor(() => {
      const el = screen.getByText('99')
      expect(el.className).toContain('color-loss-bg')
      expect(el.className).not.toContain('color-profit-bg')
    })
  })
})
