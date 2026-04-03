/**
 * Zustand store for Home Assistant state management
 */

import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'

interface Entity {
  entity_id: string
  state: string
  attributes: Record<string, any>
}

interface HAStore {
  connected: boolean
  setConnected: (connected: boolean) => void
  
  status: string
  setStatus: (status: string) => void
  
  entities: Entity[]
  setEntities: (entities: Entity[]) => void
  updateEntity: (entity: Entity) => void
  
  error: string | null
  setError: (error: string | null) => void
}

export const useHAStore = create<HAStore>()(
  subscribeWithSelector((set) => ({
    connected: false,
    setConnected: (connected) => set({ connected }),
    
    status: 'loading',
    setStatus: (status) => set({ status }),
    
    entities: [],
    setEntities: (entities) => set({ entities }),
    updateEntity: (entity) => set((state) => ({
      entities: [
        ...state.entities.filter((e) => e.entity_id !== entity.entity_id),
        entity
      ]
    })),
    
    error: null,
    setError: (error) => set({ error })
  }))
)
