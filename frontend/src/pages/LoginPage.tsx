import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TrendingUp, Loader2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { ApiError } from '@/lib/api/client'
import { Input } from '@/components/ui/input'
import { PasswordInput } from '@/components/ui/PasswordInput'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      void navigate('/')
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 403 ? 'Account is deactivated.' : 'Invalid email or password.')
      } else {
        setError('An unexpected error occurred.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden"
      style={{ backgroundColor: 'var(--color-surface)' }}
    >
      {/* Glow orbs */}
      <div className="pointer-events-none absolute inset-0" aria-hidden>
        <div className="absolute -top-32 -left-32 w-[480px] h-[480px] rounded-full opacity-20"
          style={{ background: 'radial-gradient(circle, var(--color-accent) 0%, transparent 70%)' }} />
        <div className="absolute -bottom-48 -right-24 w-[560px] h-[560px] rounded-full opacity-10"
          style={{ background: 'radial-gradient(circle, var(--color-accent) 0%, transparent 70%)' }} />
      </div>

      {/* Subtle grid overlay */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.04]" aria-hidden
        style={{
          backgroundImage:
            'linear-gradient(var(--color-text) 1px, transparent 1px), linear-gradient(90deg, var(--color-text) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      {/* Card */}
      <div className="relative z-10 w-full max-w-[400px] mx-4">
        <div className="rounded-2xl border border-(--color-border-strong) p-8 shadow-2xl"
          style={{ backgroundColor: 'var(--color-surface-2)' }}
        >
          {/* Brand */}
          <div className="flex flex-col items-center mb-8">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
              style={{ background: 'linear-gradient(135deg, var(--color-accent) 0%, #1e3a8a 100%)' }}
            >
              <TrendingUp size={22} className="text-white" />
            </div>
            <h1 className="font-mono font-bold tracking-widest text-lg"
              style={{ color: 'var(--color-accent)', letterSpacing: '0.14em' }}>
              TRADING PLATFORM
            </h1>
            <p className="text-xs mt-1.5" style={{ color: 'var(--color-text-muted)' }}>
              Intelligent algo-trading for NSE / BSE
            </p>
          </div>

          <form onSubmit={(e) => void handleSubmit(e)} noValidate className="space-y-4">
            {/* Email */}
            <div className="space-y-1.5">
              <label
                htmlFor="email"
                className="block text-xs font-medium"
                style={{ color: 'var(--color-text-muted)' }}
              >
                Email
              </label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoComplete="email"
                className="w-full"
              />
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label
                htmlFor="password"
                className="block text-xs font-medium"
                style={{ color: 'var(--color-text-muted)' }}
              >
                Password
              </label>
              <PasswordInput
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
                className="w-full"
              />
            </div>

            {/* Error */}
            {error && (
              <p className="text-xs" style={{ color: 'var(--color-loss)' }}>
                {error}
              </p>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 h-9 rounded-md text-sm font-semibold transition-opacity disabled:opacity-60 mt-2"
              style={{ backgroundColor: 'var(--color-accent)', color: '#fff' }}
            >
              {loading && <Loader2 size={14} className="animate-spin" />}
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
