import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Popover } from '@/components/ui/popover'

describe('Popover', () => {
  it('renders panel in document.body, not inside trigger parent', () => {
    render(
      <div data-testid="trigger-parent">
        <Popover
          trigger={<button>Open</button>}
          align="end"
        >
          <div data-testid="panel-content">Panel</div>
        </Popover>
      </div>
    )

    fireEvent.click(screen.getByRole('button', { name: 'Open' }))

    const panel = screen.getByTestId('panel-content')
    expect(document.body.contains(panel)).toBe(true)

    const triggerParent = screen.getByTestId('trigger-parent')
    expect(triggerParent.contains(panel)).toBe(false)
  })

  it('closes when clicking outside', () => {
    render(
      <>
        <div data-testid="outside">Outside</div>
        <Popover trigger={<button>Open</button>}>
          <div data-testid="panel-content">Panel</div>
        </Popover>
      </>
    )

    fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    expect(screen.getByTestId('panel-content')).toBeInTheDocument()

    fireEvent.mouseDown(screen.getByTestId('outside'))
    expect(screen.queryByTestId('panel-content')).not.toBeInTheDocument()
  })

  it('closes on Escape', () => {
    render(
      <Popover trigger={<button>Open</button>}>
        <div data-testid="panel-content">Panel</div>
      </Popover>
    )

    fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    expect(screen.getByTestId('panel-content')).toBeInTheDocument()

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByTestId('panel-content')).not.toBeInTheDocument()
  })

  it('toggles open/closed on trigger click', () => {
    render(
      <Popover trigger={<button>Open</button>}>
        <div data-testid="panel-content">Panel</div>
      </Popover>
    )

    expect(screen.queryByTestId('panel-content')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    expect(screen.getByTestId('panel-content')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    expect(screen.queryByTestId('panel-content')).not.toBeInTheDocument()
  })
})
