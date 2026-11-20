import { Alert, Button, Input, List, Steps, Typography } from 'antd'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '../api/http'
import {
  readCreatedAdministrator,
  sendOnboardingMessage,
  startOnboarding,
  type OnboardingSession,
} from '../api/onboarding-api'

const STEP_TITLES = ['Organization', 'Knowledge base', 'Checklist', 'Administrator'] as const

interface UserMessage {
  id: string
  kind: 'user'
  text: string
}

interface AssistantMessage {
  id: string
  kind: 'assistant'
  text: string
}

interface TypingMessage {
  id: string
  kind: 'typing'
}

type ChatMessage = UserMessage | AssistantMessage | TypingMessage

const nextId = () => crypto.randomUUID()

const NARROW_STEPS = '(max-width: 1100px)'

const useVerticalSteps = () => {
  const [vertical, setVertical] = useState(() => window.matchMedia(NARROW_STEPS).matches)

  useEffect(() => {
    const media = window.matchMedia(NARROW_STEPS)
    const update = () => setVertical(media.matches)
    update()
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])

  return vertical
}

const stepIndex = (session: OnboardingSession) => {
  const done = [
    session.industry_selected,
    session.kb_assigned,
    session.checklists_created,
    session.admin_created,
  ]
  const pending = done.findIndex((item) => !item)
  return pending === -1 ? done.length : pending
}

const MessageBody = ({ message }: { message: ChatMessage }) => {
  if (message.kind === 'typing') {
    return (
      <>
        <span className="ai-agent-role">Onboarding Assistant</span>
        <span role="status">Typing...</span>
      </>
    )
  }

  return (
    <>
      <span className="ai-agent-role">
        {message.kind === 'user' ? 'You' : 'Onboarding Assistant'}
      </span>
      <Typography.Paragraph className="ai-agent-answer">{message.text}</Typography.Paragraph>
    </>
  )
}

export const OnboardingPage = () => {
  const navigate = useNavigate()
  const verticalSteps = useVerticalSteps()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [flags, setFlags] = useState<OnboardingSession | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    startOnboarding()
      .then((session) => {
        if (!alive.current) {
          return
        }
        setSessionId(session.session_id)
        setFlags(session)
        setMessages([{ id: nextId(), kind: 'assistant', text: session.reply }])
      })
      .catch((err: unknown) => {
        if (!alive.current) {
          return
        }
        setError(err instanceof ApiError ? err.message : 'Could not start onboarding.')
      })
      .finally(() => {
        if (alive.current) {
          setPending(false)
        }
      })
    return () => {
      alive.current = false
    }
  }, [])

  const send = async () => {
    const message = draft.trim()
    if (message.length === 0 || pending || sessionId === null) {
      return
    }

    const typingId = nextId()
    setDraft('')
    setError(null)
    setPending(true)
    setMessages((current) => [
      ...current,
      { id: nextId(), kind: 'user', text: message },
      { id: typingId, kind: 'typing' },
    ])

    try {
      const result = await sendOnboardingMessage(sessionId, message)
      if (!alive.current) {
        return
      }
      setFlags(result)
      setMessages((current) =>
        current.map((item) =>
          item.id === typingId ? { id: typingId, kind: 'assistant', text: result.reply } : item,
        ),
      )
      if (result.admin_created) {
        const created = readCreatedAdministrator(result.reply, message)
        if (created) {
          navigate('/login', { replace: true, state: created })
          return
        }
        setError(
          'The organization was saved, but the sign-in page did not receive the administrator email.',
        )
      }
    } catch (err: unknown) {
      if (!alive.current) {
        return
      }
      setMessages((current) => current.filter((item) => item.id !== typingId))
      setError(err instanceof ApiError ? err.message : 'Could not continue onboarding.')
    } finally {
      if (alive.current) {
        setPending(false)
      }
    }
  }

  const progress = flags ?? {
    industry_selected: false,
    kb_assigned: false,
    checklists_created: false,
    admin_created: false,
    session_id: '',
    reply: '',
    knowledge_base_ids: null,
    tenant_id: null,
  }

  return (
    <div className="onboarding-card">
      <Typography.Title level={2}>Register your organization</Typography.Title>
      <div className="onboarding-steps" aria-label="Onboarding progress">
        <Steps
          orientation={verticalSteps ? 'vertical' : 'horizontal'}
          current={stepIndex(progress)}
          items={STEP_TITLES.map((title, index) => ({
            title,
            status: index < stepIndex(progress) ? 'finish' : undefined,
          }))}
        />
      </div>
      {error && <Alert type="error" showIcon className="auth-alert" title={error} />}
      <List
        className="ai-agent-messages"
        dataSource={messages}
        rowKey="id"
        locale={{ emptyText: 'Starting the conversation.' }}
        renderItem={(message) => (
          <List.Item>
            <MessageBody message={message} />
          </List.Item>
        )}
      />
      <div className="ai-agent-composer">
        <Input.TextArea
          rows={3}
          value={draft}
          placeholder="North Plant, automotive"
          aria-label="Message"
          disabled={pending || sessionId === null}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault()
              void send()
            }
          }}
        />
        <Button
          type="primary"
          onClick={() => {
            void send()
          }}
          disabled={pending || sessionId === null || draft.trim().length === 0}
        >
          Send
        </Button>
      </div>
    </div>
  )
}
