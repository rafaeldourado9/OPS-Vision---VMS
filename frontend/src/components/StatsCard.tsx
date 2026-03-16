import { type ReactNode } from 'react'
import { cn } from '../lib/utils'

interface StatsCardProps {
  label: string
  value: number | string
  icon: ReactNode
  color?: string
}

export default function StatsCard({ label, value, icon, color = 'bg-vms-accent' }: StatsCardProps) {
  return (
    <div className="bg-vms-card rounded-xl p-4 flex items-center justify-between min-w-[160px]">
      <div>
        <p className="text-vms-muted text-xs mb-1">{label}</p>
        <p className="text-2xl font-bold">{value}</p>
      </div>
      <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', color)}>
        {icon}
      </div>
    </div>
  )
}
