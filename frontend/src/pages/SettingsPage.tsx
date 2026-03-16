import { Settings } from 'lucide-react'

export default function SettingsPage() {
  return (
    <div>
      <h1 className="text-xl font-bold mb-6">Configurações</h1>
      <div className="bg-vms-card rounded-xl p-8 text-center max-w-md mx-auto">
        <Settings size={48} className="mx-auto mb-3 text-vms-muted opacity-40" />
        <p className="text-vms-muted">Em desenvolvimento</p>
        <p className="text-vms-muted-dark text-sm mt-1">
          Configurações de tenant, integrações e preferências estarão disponíveis em breve.
        </p>
      </div>
    </div>
  )
}
