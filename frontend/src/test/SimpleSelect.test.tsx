import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { SimpleSelect } from '@/components/ui/simple-select'

describe('SimpleSelect', () => {
  it('renders the selected option LABEL, not the raw value', () => {
    // Regression (2026-07-11): base-ui's Value renders the raw value by
    // default — invisible while every caller had value≡label; watchlist
    // scopes select by id ("4") and must display the name ("Momo").
    render(
      <SimpleSelect
        value="4"
        onChange={vi.fn()}
        options={[
          { value: '4', label: 'Momo' },
          { value: '7', label: 'Core' },
        ]}
      />,
    )
    expect(screen.getByRole('combobox')).toHaveTextContent('Momo')
    expect(screen.getByRole('combobox')).not.toHaveTextContent('4')
  })

  it('shows the placeholder when nothing is selected', () => {
    render(
      <SimpleSelect
        value=""
        onChange={vi.fn()}
        placeholder="Pick one"
        options={[{ value: '4', label: 'Momo' }]}
      />,
    )
    expect(screen.getByRole('combobox')).toHaveTextContent('Pick one')
  })
})
