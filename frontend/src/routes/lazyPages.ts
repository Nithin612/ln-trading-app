import { lazy, type ComponentType } from 'react'

// Route-level code splitting — every page (and its heavy chart deps:
// lightweight-charts, recharts) is a lazy chunk loaded behind the AppShell
// Suspense boundary. Kept out of router.tsx so that file stays a pure route
// table (react-refresh wants component definitions in their own module).
// `named` maps a named export to the { default } shape React.lazy expects.
const named = (p: Promise<Record<string, unknown>>, key: string) =>
  p.then((m) => ({ default: m[key] as ComponentType }))

export const UsersPage = lazy(() => named(import('@/pages/admin/UsersPage'), 'UsersPage'))
export const SettingsPage = lazy(() => named(import('@/pages/admin/SettingsPage'), 'SettingsPage'))
export const StocksPage = lazy(() => named(import('@/features/stocks/StocksPage'), 'StocksPage'))
export const StockDetailPage = lazy(() => named(import('@/pages/stocks/StockDetailPage'), 'StockDetailPage'))
export const ScreenerPage = lazy(() => named(import('@/features/screener/ScreenerPage'), 'ScreenerPage'))
export const WatchlistsPage = lazy(() => named(import('@/features/watchlists/WatchlistsPage'), 'WatchlistsPage'))
export const CategoriesPage = lazy(() => named(import('@/features/categories/CategoriesPage'), 'CategoriesPage'))
export const FiiDiiPage = lazy(() => named(import('@/features/market/FiiDiiPage'), 'FiiDiiPage'))
export const DashboardPage = lazy(() => named(import('@/features/dashboard/DashboardPage'), 'DashboardPage'))
export const KiteConnectPage = lazy(() => import('@/features/broker/KiteConnectPage'))
export const FilingsPage = lazy(() => named(import('@/features/filings/FilingsPage'), 'FilingsPage'))
export const ProfilePage = lazy(() => named(import('@/features/profile/ProfilePage'), 'ProfilePage'))
export const PositionsPage = lazy(() => named(import('@/features/trading/PositionsPage'), 'PositionsPage'))
export const TradeHistoryPage = lazy(() => named(import('@/features/trading/TradeHistoryPage'), 'TradeHistoryPage'))
export const StrategyLabPage = lazy(() => named(import('@/features/strategy/StrategyLabPage'), 'StrategyLabPage'))
export const JournalPage = lazy(() => named(import('@/features/journal/JournalPage'), 'JournalPage'))
export const PortfolioPage = lazy(() => named(import('@/features/portfolio/PortfolioPage'), 'PortfolioPage'))
export const StylePage = lazy(() => named(import('@/features/styles/StylePage'), 'StylePage'))
export const GoLivePage = lazy(() => named(import('@/features/golive/GoLivePage'), 'GoLivePage'))
export const OutcomesPage = lazy(() => named(import('@/features/analytics/OutcomesPage'), 'OutcomesPage'))
