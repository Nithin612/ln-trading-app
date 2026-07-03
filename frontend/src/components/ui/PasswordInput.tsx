import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface PasswordInputProps extends React.ComponentProps<'input'> {
  className?: string
}

export function PasswordInput({ className, ...props }: PasswordInputProps) {
  const [shown, setShown] = useState(false)

  return (
    <div className="relative">
      <Input
        type={shown ? 'text' : 'password'}
        className={cn('pr-10', className)}
        {...props}
      />
      <button
        type="button"
        onClick={() => setShown((s) => !s)}
        aria-label={shown ? 'Hide characters' : 'Show characters'}
        className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md text-[--color-text-muted] hover:text-[--color-text] hover:bg-[--color-surface-2] transition-colors duration-150"
        tabIndex={-1}
      >
        {shown ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
      </button>
    </div>
  )
}
