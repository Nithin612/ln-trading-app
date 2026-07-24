interface UserAvatarProps {
  name: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0][0].toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

const SIZE = {
  sm: { outer: 'w-6 h-6', text: 'text-[10px]' },
  md: { outer: 'w-8 h-8', text: 'text-xs' },
  lg: { outer: 'w-10 h-10', text: 'text-sm' },
}

export function UserAvatar({ name, size = 'md', className = '' }: UserAvatarProps) {
  const { outer, text } = SIZE[size]
  return (
    <div
      className={`${outer} rounded-full flex items-center justify-center font-semibold flex-shrink-0 select-none ${className}`}
      style={{
        // Solid accent + its AA-tuned foreground (same pairing as buttons) —
        // a gradient's two stops can have opposite lightness per theme, so a
        // single foreground can't contrast with both.
        background: 'var(--color-accent)',
        color: 'var(--color-primary-foreground)',
        letterSpacing: '0.02em',
      }}
    >
      <span className={text}>{initials(name)}</span>
    </div>
  )
}
