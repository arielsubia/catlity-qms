import { apiRequest } from './http'

export interface AppNotification {
  id: string
  kind: string
  title: string
  finding_id: string | null
  read: boolean
  created_at: string | null
  status: string
}

export interface NotificationListResponse {
  items: AppNotification[]
  unread_count: number
}

export const findingPath = (findingId: string | null): string =>
  findingId ? `/findings?finding=${encodeURIComponent(findingId)}` : '/findings'

export const listNotifications = (limit: number): Promise<NotificationListResponse> =>
  apiRequest<NotificationListResponse>(`/api/v1/notifications?limit=${limit}`)

export const markNotificationRead = (id: string): Promise<{ id: string; read: boolean }> =>
  apiRequest<{ id: string; read: boolean }>(`/api/v1/notifications/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ read: true }),
  })

export const markAllNotificationsRead = (): Promise<{ updated: number }> =>
  apiRequest<{ updated: number }>('/api/v1/notifications/read', { method: 'POST' })
