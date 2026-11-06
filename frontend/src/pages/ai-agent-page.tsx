import { Alert, Button, Input, List, Popover, Typography } from 'antd'
import { useEffect, useRef, useState } from 'react'

import { ApiError } from '../api/http'
import { queryNormative, type NormativeReference } from '../api/normative-api'

const MAX_QUESTION_LENGTH = 1000

interface UserMessage {
  id: string
  kind: 'user'
  text: string
}

interface AssistantMessage {
  id: string
  kind: 'assistant'
  text: string
  references: NormativeReference[]
}

interface TypingMessage {
  id: string
  kind: 'typing'
}

type ChatMessage = UserMessage | AssistantMessage | TypingMessage

const nextId = () => crypto.randomUUID()

// The notes are plain text in a private bucket: document and section are the file name.
const ReferenceLink = ({ reference }: { reference: NormativeReference }) => (
  <li>
    <Popover
      trigger="click"
      title="Study note"
      content={
        <div>
          <p>Document: {reference.document}</p>
          <p>Section: {reference.section}</p>
          <p>This note is stored in the private knowledge base bucket and has no public page.</p>
        </div>
      }
    >
      <Typography.Link
        href={`#${encodeURIComponent(reference.document)}`}
        onClick={(event) => {
          event.preventDefault()
        }}
      >
        {reference.document}
      </Typography.Link>
    </Popover>
  </li>
)

const MessageBody = ({ message }: { message: ChatMessage }) => {
  if (message.kind === 'typing') {
    return (
      <>
        <span className="ai-agent-role">Normative Advisor</span>
        <span role="status">Typing...</span>
      </>
    )
  }

  if (message.kind === 'user') {
    return (
      <>
        <span className="ai-agent-role">You</span>
        <Typography.Paragraph className="ai-agent-answer">{message.text}</Typography.Paragraph>
      </>
    )
  }

  return (
    <>
      <span className="ai-agent-role">Normative Advisor</span>
      <Typography.Paragraph className="ai-agent-answer">{message.text}</Typography.Paragraph>
      {message.references.length > 0 && (
        <ul className="ai-agent-references">
          {message.references.map((reference, index) => (
            <ReferenceLink key={`${message.id}-${index}`} reference={reference} />
          ))}
        </ul>
      )}
    </>
  )
}

export const AiAgentPage = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  const send = async () => {
    const question = draft.trim()
    if (question.length === 0 || pending) {
      return
    }

    const typingId = nextId()
    setDraft('')
    setError(null)
    setPending(true)
    setMessages((current) => [
      ...current,
      { id: nextId(), kind: 'user', text: question },
      { id: typingId, kind: 'typing' },
    ])

    try {
      const result = await queryNormative(question)
      if (!alive.current) {
        return
      }
      setMessages((current) =>
        current.map((item) =>
          item.id === typingId
            ? {
                id: typingId,
                kind: 'assistant',
                text: result.answer,
                references: result.references,
              }
            : item,
        ),
      )
    } catch (err: unknown) {
      if (!alive.current) {
        return
      }
      setMessages((current) => current.filter((item) => item.id !== typingId))
      setError(err instanceof ApiError ? err.message : 'Could not ask the normative advisor.')
    } finally {
      if (alive.current) {
        setPending(false)
      }
    }
  }

  return (
    <div className="ai-agent-page">
      <Typography.Title level={2}>AI Agent</Typography.Title>
      {error && <Alert type="error" showIcon className="auth-alert" title={error} />}
      <List
        className="ai-agent-messages"
        dataSource={messages}
        rowKey="id"
        locale={{ emptyText: 'Ask a question about the study notes.' }}
        renderItem={(message) => (
          <List.Item>
            <MessageBody message={message} />
          </List.Item>
        )}
      />
      <div className="ai-agent-composer">
        <Input.TextArea
          rows={3}
          maxLength={MAX_QUESTION_LENGTH}
          showCount
          value={draft}
          placeholder="Ask about the study notes"
          aria-label="Question"
          disabled={pending}
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
          disabled={pending || draft.trim().length === 0}
        >
          Send
        </Button>
      </div>
    </div>
  )
}
