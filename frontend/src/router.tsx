import { Navigate, createBrowserRouter } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { RequireAdmin, RequireAuth } from '@/components/auth/ProtectedRoute'
import { LoginPage } from '@/pages/LoginPage'
import { UsersPage } from '@/pages/admin/UsersPage'
import { SettingsPage } from '@/pages/admin/SettingsPage'
import { StocksPage } from '@/features/stocks/StocksPage'
import { StockDetailPage } from '@/pages/stocks/StockDetailPage'
import { ScreenerPage } from '@/features/screener/ScreenerPage'
import { WatchlistsPage } from '@/features/watchlists/WatchlistsPage'
import { CategoriesPage } from '@/features/categories/CategoriesPage'
import { FiiDiiPage } from '@/features/market/FiiDiiPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import KiteConnectPage from '@/features/broker/KiteConnectPage'
import { FilingsPage } from '@/features/filings/FilingsPage'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { PositionsPage } from '@/features/trading/PositionsPage'
import { TradeHistoryPage } from '@/features/trading/TradeHistoryPage'
import { StrategyLabPage } from '@/features/strategy/StrategyLabPage'
import { JournalPage } from '@/features/journal/JournalPage'
import { PortfolioPage } from '@/features/portfolio/PortfolioPage'
import { StylePage } from '@/features/styles/StylePage'

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },
      { path: 'dashboard',             element: <DashboardPage /> },
      { path: 'styles/:style',         element: <StylePage /> },
      { path: 'stocks',                element: <StocksPage /> },
      { path: 'stocks/:id',            element: <StockDetailPage /> },
      { path: 'screener',              element: <ScreenerPage /> },
      { path: 'watchlists',            element: <WatchlistsPage /> },
      { path: 'categories',            element: <CategoriesPage /> },
      { path: 'market/fii-dii',        element: <FiiDiiPage /> },
      { path: 'filings',               element: <FilingsPage /> },
      { path: 'profile',               element: <ProfilePage /> },
      { path: 'trading/positions',     element: <PositionsPage /> },
      { path: 'trading/history',       element: <TradeHistoryPage /> },
      { path: 'strategy',              element: <StrategyLabPage /> },
      { path: 'journal',               element: <JournalPage /> },
      { path: 'portfolio',             element: <PortfolioPage /> },
      {
        path: 'broker/kite',
        element: <RequireAdmin><KiteConnectPage /></RequireAdmin>,
      },
      {
        path: 'admin/users',
        element: <RequireAdmin><UsersPage /></RequireAdmin>,
      },
      {
        path: 'admin/settings',
        element: <RequireAdmin><SettingsPage /></RequireAdmin>,
      },
    ],
  },
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
])
