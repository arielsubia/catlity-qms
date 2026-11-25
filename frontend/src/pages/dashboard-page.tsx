import { Typography } from 'antd'
import { useEffect, useRef, useState } from 'react'

import { getEmbedUrl } from '../api/quicksight-api'
import { useAuth } from '../auth/use-auth'
import { refreshDelayMs } from '../dashboard/embed-session'
import { canViewDashboard } from '../dashboard/permissions'

const UNAVAILABLE = 'Dashboard is not available yet.'

export const DashboardPage = () => {
  const { user } = useAuth()
  if (!user || !canViewDashboard(user.role)) {
    return (
      <>
        <Typography.Title level={2}>Dashboard</Typography.Title>
        <Typography.Paragraph>This section is not available yet.</Typography.Paragraph>
      </>
    )
  }

  return <DashboardEmbed />
}

const DashboardEmbed = () => {
  const [embedUrl, setEmbedUrl] = useState<string | null>(null)
  const [unavailable, setUnavailable] = useState(false)
  const embedUrlRef = useRef<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let timer = 0

    const load = async () => {
      try {
        const result = await getEmbedUrl()
        if (cancelled) {
          return
        }
        embedUrlRef.current = result.embed_url
        setEmbedUrl(result.embed_url)
        setUnavailable(false)
        const delay = refreshDelayMs(result.expires_at)
        if (delay > 0) {
          timer = window.setTimeout(() => {
            void load()
          }, delay)
        }
      } catch {
        if (!cancelled && embedUrlRef.current === null) {
          setUnavailable(true)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [])

  return (
    <>
      <Typography.Title level={2}>Dashboard</Typography.Title>
      {embedUrl && (
        <iframe title="Compliance dashboard" src={embedUrl} className="dashboard-frame" />
      )}
      {!embedUrl && unavailable && <Typography.Paragraph>{UNAVAILABLE}</Typography.Paragraph>}
    </>
  )
}
