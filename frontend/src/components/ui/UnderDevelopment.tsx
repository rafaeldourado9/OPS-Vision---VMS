import { Construction } from 'lucide-react'

interface Props {
  title: string
}

export function UnderDevelopment({ title }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-32 gap-4 animate-fade-in">
      <div className="w-16 h-16 rounded-2xl flex items-center justify-center"
        style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}>
        <Construction size={28} style={{ color: 'var(--warning)' }} />
      </div>
      <div className="text-center">
        <p className="text-sm font-semibold text-t1">{title}</p>
        <p className="text-xs text-t3 mt-1">Em desenvolvimento</p>
      </div>
    </div>
  )
}
