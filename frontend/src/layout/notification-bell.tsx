import { Badge, Button, Dropdown } from 'antd'
import { useCallback, useContext, useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import {
  findingPath,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type AppNotification,
} from '../api/notifications-api'
import { NotificationInboxContext } from './notification-inbox-context'

const BellIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path
      fill="currentColor"
      d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22zm7-6V11a7 7 0 0 0-5-6.71V4a2 2 0 1 0-4 0v.29A7 7 0 0 0 5 11v5l-2 2v1h18v-1l-2-2z"
    />
  </svg>
)

export const NotificationBell = () => {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const inbox = useContext(NotificationInboxContext)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<AppNotification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [markingAll, setMarkingAll] = useState(false)

  const load = useCallback(() => {
    void listNotifications(5)
      .then((result) => {
        setItems(result.items.slice(0, 5))
        setUnreadCount(result.unread_count)
      })
      .catch(() => {
        setItems([])
        setUnreadCount(0)
      })
  }, [])

  useEffect(() => {
    load()
  }, [load, pathname, inbox?.revision])

  const openNotification = async (item: AppNotification) => {
    setOpen(false)
    if (!item.read) {
      try {
        await markNotificationRead(item.id)
        inbox?.refresh()
      } catch {
        load()
        return
      }
    }
    navigate(findingPath(item.finding_id))
  }

  const markAll = async () => {
    setMarkingAll(true)
    try {
      await markAllNotificationsRead()
      setItems((current) => current.map((item) => ({ ...item, read: true })))
      setUnreadCount(0)
      inbox?.refresh()
    } catch {
      load()
    } finally {
      setMarkingAll(false)
    }
  }

  return (
    <Dropdown
      open={open}
      trigger={['click']}
      onOpenChange={setOpen}
      popupRender={() => (
        <div className="notification-panel">
          {items.length === 0 ? (
            <p className="notification-empty">No notifications</p>
          ) : (
            <ul className="notification-list">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className={
                      item.read ? 'notification-item' : 'notification-item notification-item-unread'
                    }
                    onClick={() => void openNotification(item)}
                  >
                    {item.title}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="notification-panel-actions">
            <Button
              type="link"
              onClick={() => {
                setOpen(false)
                navigate('/notifications')
              }}
            >
              View all
            </Button>
            <Button
              type="link"
              disabled={unreadCount === 0}
              loading={markingAll}
              onClick={() => void markAll()}
            >
              Mark all as read
            </Button>
          </div>
        </div>
      )}
    >
      <span className="notification-bell">
        <Badge count={unreadCount}>
          <Button aria-label="Notifications" type="text">
            <BellIcon />
          </Button>
        </Badge>
      </span>
    </Dropdown>
  )
}
