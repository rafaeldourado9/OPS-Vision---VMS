import { useState, useEffect, useCallback } from 'react'
import { cameraService } from '@/services/api'
import type { Camera } from '@/types'
import toast from 'react-hot-toast'

export function useCameras() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)

  const fetch = useCallback(async () => {
    setLoading(true)
    try {
      const data = await cameraService.list()
      setCameras(data.results)
    } catch {
      toast.error('Erro ao carregar câmeras')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetch() }, [fetch])

  const remove = async (id: string, name: string) => {
    try {
      await cameraService.delete(id)
      setCameras(prev => prev.filter(c => c.id !== id))
      toast.success(`"${name}" removida`)
    } catch {
      toast.error('Erro ao remover câmera')
    }
  }

  return { cameras, loading, refresh: fetch, remove }
}
