import { Navigate, createBrowserRouter } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { RequireAdmin, RequireAuth } from '@/components/auth/ProtectedRoute'
import { LoginPage } from '@/pages/LoginPage'
// The shell + auth load eagerly; every page is a lazy chunk (see lazyPages).
import {
  CategoriesPage, DashboardPage, FiiDiiPage, FilingsPage, GoLivePage, JournalPage,
  KiteConnectPage, OutcomesPage, PortfolioPage, PositionsPage, ProfilePage, ScreenerPage,
  SettingsPage, StockDetailPage, StocksPage, StrategyLabPage, StylePage, TradeHistoryPage,
  UsersPage, WatchlistsPage,
} from '@/routes/lazyPages'

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
      { path: 'go-live',               element: <GoLivePage /> },
      { path: 'strategy',              element: <StrategyLabPage /> },
      { path: 'journal',               element: <JournalPage /> },
      { path: 'portfolio',             element: <PortfolioPage /> },
      { path: 'analytics/outcomes',    element: <OutcomesPage /> },
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
