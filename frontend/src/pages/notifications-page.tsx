import { Alert, Button, Typography } from 'antd'
import { useContext, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '../api/http'
import {
  findingPath,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type AppNotification,
} from '../api/notifications-api'
import { useAuth } from '../auth/use-auth'
import { NotificationInboxContext } from '../layout/notification-inbox-context'

const HISTORY_LIMIT = 100

export const NotificationsPage = () => {
  const { user } = useAuth()
  const navigate = useNavigate()
  const inbox = useContext(NotificationInboxContext)
  const [items, setItems] = useState<AppNotification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [markingAll, setMarkingAll] = useState(false)

  useEffect(() => {
    if (!user) {
      return
    }
    let active = true
    void listNotifications(HISTORY_LIMIT)
      .then((result) => {
        if (!active) {
          return
        }
        setItems(result.items)
        setUnreadCount(result.unread_count)
        setError(null)
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof ApiError ? err.message : 'Could not load notifications.')
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [user])

  if (!user) {
    return null
  }

  const markOne = async (id: string) => {
    setPendingId(id)
    setError(null)
    try {
      await markNotificationRead(id)
      setItems((current) =>
        current.map((item) => (item.id === id ? { ...item, read: true } : item)),
      )
      setUnreadCount((count) => Math.max(0, count - 1))
      inbox?.refresh()
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : 'Could not mark the notification as read.')
    } finally {
      setPendingId(null)
    }
  }

  const markAll = async () => {
    setMarkingAll(true)
    setError(null)
    try {
      await markAllNotificationsRead()
      setItems((current) => current.map((item) => ({ ...item, read: true })))
      setUnreadCount(0)
      inbox?.refresh()
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : 'Could not mark notifications as read.')
    } finally {
      setMarkingAll(false)
    }
  }

  const openNotification = async (item: AppNotification) => {
    if (!item.read) {
      try {
        await markNotificationRead(item.id)
        inbox?.refresh()
      } catch (err: unknown) {
        setError(err instanceof ApiError ? err.message : 'Could not mark the notification as read.')
        return
      }
    }
    navigate(findingPath(item.finding_id))
  }

  return (
    <>
      <div className="audits-header">
        <Typography.Title level={2}>Notifications</Typography.Title>
        <Button disabled={unreadCount === 0} loading={markingAll} onClick={() => void markAll()}>
          Mark all as read
        </Button>
      </div>
      {error && <Alert type="error" showIcon className="auth-alert" title={error} />}
      {loading ? (
        <Typography.Paragraph>Loading notifications.</Typography.Paragraph>
      ) : items.length === 0 ? (
        <Typography.Paragraph>No notifications</Typography.Paragraph>
      ) : (
        <ul className="notification-history">
          {items.map((item) => (
            <li key={item.id} className={item.read ? undefined : 'notification-item-unread'}>
              <button
                type="button"
                className="notification-item"
                onClick={() => void openNotification(item)}
              >
                {item.title}
              </button>
              {item.created_at && <span className="notification-when">{item.created_at}</span>}
              {!item.read && (
                <Button loading={pendingId === item.id} onClick={() => void markOne(item.id)}>
                  Mark as read
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
