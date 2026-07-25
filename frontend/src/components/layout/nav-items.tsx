import {
  LayoutDashboard, TrendingUp, SlidersHorizontal, ListChecks, Tags, Building2,
  FileText, Briefcase, History, FlaskConical, BookOpen, Wallet, Zap, Users, Settings,
  Activity, Layers, Landmark,
} from 'lucide-react'

export interface NavItem {
  to: string
  icon: React.ReactNode
  label: string
  warnIcon?: string
}

export interface NavGroup {
  title: string
  items: NavItem[]
  adminOnly?: boolean
}

/** Grouped information architecture for the sidebar (Phase-5 IA overhaul). */
export const NAV_GROUPS: NavGroup[] = [
  {
    title: 'Markets',
    items: [
      { to: '/dashboard',      icon: <LayoutDashboard size={18} />,   label: 'Dashboard' },
      { to: '/stocks',         icon: <TrendingUp size={18} />,        label: 'Stocks' },
      { to: '/screener',       icon: <SlidersHorizontal size={18} />, label: 'Screener' },
      { to: '/watchlists',     icon: <ListChecks size={18} />,        label: 'Watchlists' },
      { to: '/categories',     icon: <Tags size={18} />,              label: 'Categories' },
      { to: '/market/fii-dii', icon: <Building2 size={18} />,         label: 'FII / DII' },
      { to: '/filings',        icon: <FileText size={18} />,          label: 'Filings' },
    ],
  },
  {
    title: 'Styles',
    items: [
      { to: '/styles/intraday',   icon: <Activity size={18} />,   label: 'Intraday' },
      { to: '/styles/swing',      icon: <TrendingUp size={18} />, label: 'Swing' },
      { to: '/styles/fno',        icon: <Layers size={18} />,     label: 'F&O' },
      { to: '/styles/investment', icon: <Landmark size={18} />,   label: 'Investment' },
    ],
  },
  {
    title: 'Trading',
    items: [
      { to: '/trading/positions', icon: <Briefcase size={18} />, label: 'Positions' },
      { to: '/trading/history',   icon: <History size={18} />,   label: 'Trade History' },
    ],
  },
  {
    title: 'Analysis',
    items: [
      { to: '/strategy',  icon: <FlaskConical size={18} />, label: 'Strategy Lab' },
      { to: '/journal',   icon: <BookOpen size={18} />,     label: 'Journal' },
      { to: '/portfolio', icon: <Wallet size={18} />,       label: 'Portfolio' },
    ],
  },
  {
    title: 'Admin',
    adminOnly: true,
    items: [
      { to: '/broker/kite',    icon: <Zap size={18} />,      label: 'Kite' },
      { to: '/admin/users',    icon: <Users size={18} />,    label: 'Users' },
      { to: '/admin/settings', icon: <Settings size={18} />, label: 'Settings' },
    ],
  },
]

export function isNavActive(pathname: string, to: string): boolean {
  return pathname === to || (to !== '/dashboard' && pathname.startsWith(to))
}
