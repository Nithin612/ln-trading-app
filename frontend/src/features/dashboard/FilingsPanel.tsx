import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { filingsApi } from '@/lib/api/filings'
import type { FilingOut } from '@/lib/api/filings'

const TYPE_ICONS: Record<string, string> = {
  earnings: '📊',
  board_meeting: '📋',
  dividend: '💰',
  split: '✂️',
  bonus: '🎁',
  merger: '🤝',
  agm: '🏛️',
  rating_change: '⭐',
  other: '📄',
}

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

function FilingCard({ filing }: { filing: FilingOut }) {
  return (
    <div
      style={{
        padding: '0.75rem',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        gap: '0.75rem',
        alignItems: 'flex-start',
        transition: 'background 0.1s',
      }}
      onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.background = 'var(--color-surface-3)')}
      onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.background = 'transparent')}
    >
      <span style={{ fontSize: '1rem', flexShrink: 0, marginTop: '1px' }}>
        {TYPE_ICONS[filing.filing_type] ?? '📄'}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem', flexWrap: 'wrap' }}>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              fontSize: '0.8rem',
              color: 'var(--color-accent)',
            }}
          >
            {filing.symbol}
          </span>
          {filing.is_high_impact && (
            <span
              style={{
                padding: '1px 5px', borderRadius: '3px', fontSize: '0.65rem',
                background: 'rgba(218,54,51,0.2)', color: 'var(--color-error)',
                border: '1px solid rgba(218,54,51,0.35)', fontWeight: 600,
              }}
            >
              HIGH IMPACT
            </span>
          )}
          <span
            style={{
              fontSize: '0.65rem', color: 'var(--color-text-muted)',
              background: 'var(--color-surface-3)',
              padding: '1px 5px', borderRadius: '3px',
            }}
          >
            {filing.source}
          </span>
        </div>
        <p
          style={{
            fontSize: '0.8rem', color: 'var(--color-text)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}
          title={filing.headline}
        >
          {filing.headline}
        </p>
        <p style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginTop: '0.25rem' }}>
          {timeAgo(filing.filing_time)}
        </p>
      </div>
    </div>
  )
}

interface Props {
  hours?: number
}

export function FilingsPanel({ hours = 24 }: Props) {
  const { accessToken } = useAuth()

  const { data, isLoading, error } = useQuery({
    queryKey: ['filings-recent', hours],
    queryFn: () => filingsApi.getRecent({ hours, limit: 50 }, accessToken!),
    enabled: !!accessToken,
    refetchInterval: 60_000,
  })

  return (
    <div
      style={{
        background: 'var(--color-surface-2)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: '400px',
      }}
    >
      <div
        style={{
          padding: '0.875rem 1rem',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <p
          style={{
            fontSize: '0.75rem', color: 'var(--color-text-muted)',
            textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600,
          }}
        >
          Live Filings
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {data && (
            <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>
              {data.total} in {hours}h
            </span>
          )}
          <Link
            to="/filings"
            style={{ fontSize: '0.7rem', color: 'var(--color-accent)', textDecoration: 'none', fontWeight: 500 }}
          >
            View all →
          </Link>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {isLoading && (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
            Loading…
          </div>
        )}
        {error && (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-error)', fontSize: '0.8rem' }}>
            Failed to load filings
          </div>
        )}
        {!isLoading && !error && data?.filings.length === 0 && (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
            No filings in the last {hours} hours
          </div>
        )}
        {data?.filings.map((f) => <FilingCard key={f.id} filing={f} />)}
      </div>
    </div>
  )
}
