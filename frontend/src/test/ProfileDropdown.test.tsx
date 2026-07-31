import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import { ProfileDropdown } from '@/components/ui/profile-dropdown'

const USER = {
  id: 1,
  email: 'nithin@example.com',
  full_name: 'Nithin Raj',
  role: 'admin',
  capital_inr: '500000',
  risk_per_trade_pct: '2',
  daily_loss_limit_pct: '3',
  max_trades_per_day: 5,
  is_active: true,
  trading_mode: 'paper', allow_offmarket_entry: false, profit_lock_enabled: false,
  created_at: '2025-01-15T00:00:00Z',
  updated_at: '2025-01-15T00:00:00Z',
}

function setup(isAdmin = true, onLogout = vi.fn()) {
  return render(
    <MemoryRouter>
      <ProfileDropdown user={USER} isAdmin={isAdmin} onLogout={onLogout} />
    </MemoryRouter>,
  )
}

describe('ProfileDropdown', () => {
  it('renders trigger button with user initials', () => {
    setup()
    expect(screen.getByTestId('profile-trigger')).toBeInTheDocument()
    expect(screen.getByText('NR')).toBeInTheDocument()
  })

  it('opens dropdown on trigger click', async () => {
    setup()
    fireEvent.click(screen.getByTestId('profile-trigger'))
    await waitFor(() => {
      expect(screen.getByText('nithin@example.com')).toBeInTheDocument()
    })
  })

  it('shows full name in dropdown header', async () => {
    setup()
    fireEvent.click(screen.getByTestId('profile-trigger'))
    await waitFor(() => {
      expect(screen.getByText('Nithin Raj')).toBeInTheDocument()
    })
  })

  it('shows Admin badge for admin user', async () => {
    setup(true)
    fireEvent.click(screen.getByTestId('profile-trigger'))
    await waitFor(() => {
      expect(screen.getByText('Admin')).toBeInTheDocument()
    })
  })

  it('shows Paper Trading badge', async () => {
    setup()
    fireEvent.click(screen.getByTestId('profile-trigger'))
    await waitFor(() => {
      expect(screen.getByText('Paper Trading')).toBeInTheDocument()
    })
  })

  it('shows My Profile and Appearance Settings links for admin', async () => {
    setup(true)
    fireEvent.click(screen.getByTestId('profile-trigger'))
    await waitFor(() => {
      expect(screen.getByText('My Profile')).toBeInTheDocument()
      expect(screen.getByText('Appearance Settings')).toBeInTheDocument()
    })
  })

  it('hides Appearance Settings link for non-admin', async () => {
    setup(false)
    fireEvent.click(screen.getByTestId('profile-trigger'))
    await waitFor(() => {
      expect(screen.queryByText('Appearance Settings')).not.toBeInTheDocument()
    })
  })

  it('calls onLogout when Sign out is clicked', async () => {
    const onLogout = vi.fn()
    setup(true, onLogout)
    fireEvent.click(screen.getByTestId('profile-trigger'))
    await waitFor(() => screen.getByText('Sign out'))
    fireEvent.click(screen.getByText('Sign out'))
    expect(onLogout).toHaveBeenCalledTimes(1)
  })

  it('closes dropdown on outside click', async () => {
    setup()
    fireEvent.click(screen.getByTestId('profile-trigger'))
    await waitFor(() => screen.getByText('Sign out'))

    fireEvent.mouseDown(document.body)
    await waitFor(() => {
      expect(screen.queryByText('Sign out')).not.toBeInTheDocument()
    })
  })
})
