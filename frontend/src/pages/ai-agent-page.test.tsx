import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/http'
import { queryNormative, type NormativeQueryResponse } from '../api/normative-api'
import { AiAgentPage } from './ai-agent-page'

vi.mock('../api/normative-api', () => ({
  queryNormative: vi.fn(),
}))

const renderPage = () => {
  render(<AiAgentPage />)
  return userEvent.setup()
}

describe('AiAgentPage', () => {
  beforeEach(() => {
    vi.mocked(queryNormative).mockReset()
  })

  it('shows the chat panel with an empty conversation', () => {
    renderPage()

    expect(screen.getByRole('heading', { level: 2, name: 'AI Agent' })).toBeInTheDocument()
    expect(screen.getByText('Ask a question about the study notes.')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Question' })).toHaveAttribute('maxlength', '1000')
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
    expect(queryNormative).not.toHaveBeenCalled()
  })

  it('keeps the thread and shows Typing... until the answer arrives', async () => {
    let resolveQuery: (value: NormativeQueryResponse) => void = () => undefined
    vi.mocked(queryNormative).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveQuery = resolve
        }),
    )
    const user = renderPage()
    await user.type(screen.getByRole('textbox', { name: 'Question' }), 'What is a quality policy?')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(screen.getByText('You')).toBeInTheDocument()
    expect(screen.getByText('What is a quality policy?')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Typing...')
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
    expect(queryNormative).toHaveBeenCalledTimes(1)
    expect(queryNormative).toHaveBeenCalledWith('What is a quality policy?')

    resolveQuery({
      answer: 'The study notes do not cover this question.',
      references: [],
    })

    expect(
      await screen.findByText('The study notes do not cover this question.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByText('What is a quality policy?')).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('appends a second question after the first answer', async () => {
    vi.mocked(queryNormative)
      .mockResolvedValueOnce({
        answer: 'A quality policy is documented.',
        references: [],
      })
      .mockResolvedValueOnce({
        answer: 'The study notes do not cover this question.',
        references: [],
      })
    const user = renderPage()
    await user.type(screen.getByRole('textbox', { name: 'Question' }), 'What is a quality policy?')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    expect(await screen.findByText('A quality policy is documented.')).toBeInTheDocument()

    await user.type(screen.getByRole('textbox', { name: 'Question' }), 'What is a batch record?')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(
      await screen.findByText('The study notes do not cover this question.'),
    ).toBeInTheDocument()
    expect(screen.getByText('What is a quality policy?')).toBeInTheDocument()
    expect(screen.getByText('A quality policy is documented.')).toBeInTheDocument()
    expect(screen.getByText('What is a batch record?')).toBeInTheDocument()
    expect(queryNormative).toHaveBeenNthCalledWith(2, 'What is a batch record?')
  })

  it('opens document and section for each study-note reference', async () => {
    vi.mocked(queryNormative).mockResolvedValue({
      answer: 'A quality policy is documented.',
      references: [
        {
          document: 'iso-9001-quality-policy.txt',
          section: 'iso-9001-quality-policy.txt',
        },
        { document: 'iso-9001-context.txt', section: '4-context' },
      ],
    })
    const user = renderPage()
    await user.type(screen.getByRole('textbox', { name: 'Question' }), 'What is a quality policy?')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    const policy = await screen.findByRole('link', { name: 'iso-9001-quality-policy.txt' })
    await user.click(policy)

    expect(await screen.findByText('Document: iso-9001-quality-policy.txt')).toBeInTheDocument()
    expect(screen.getByText('Section: iso-9001-quality-policy.txt')).toBeInTheDocument()
    expect(
      screen.getByText(
        'This note is stored in the private knowledge base bucket and has no public page.',
      ),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'iso-9001-context.txt' }))

    expect(await screen.findByText('Document: iso-9001-context.txt')).toBeInTheDocument()
    expect(screen.getByText('Section: 4-context')).toBeInTheDocument()
  })

  it('does not send a blank question', async () => {
    const user = renderPage()
    await user.type(screen.getByRole('textbox', { name: 'Question' }), '   ')

    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
    await user.keyboard('{Enter}')

    expect(queryNormative).not.toHaveBeenCalled()
    expect(screen.queryByText('You')).not.toBeInTheDocument()
  })

  it('sends on Enter and keeps a newline on Shift+Enter', async () => {
    vi.mocked(queryNormative).mockResolvedValue({
      answer: 'A quality policy is documented.',
      references: [],
    })
    const user = renderPage()
    await user.type(screen.getByRole('textbox', { name: 'Question' }), 'What is a quality policy?')
    await user.keyboard('{Shift>}{Enter}{/Shift}')

    expect(queryNormative).not.toHaveBeenCalled()
    expect(screen.getByRole('textbox', { name: 'Question' })).toHaveValue(
      'What is a quality policy?\n',
    )

    await user.keyboard('{Enter}')

    expect(queryNormative).toHaveBeenCalledWith('What is a quality policy?')
    expect(await screen.findByText('A quality policy is documented.')).toBeInTheDocument()
  })

  it('shows the API error and drops the typing indicator', async () => {
    vi.mocked(queryNormative).mockRejectedValue(
      new ApiError('Rate limit exceeded. Maximum 10 queries per minute.', 429),
    )
    const user = renderPage()
    await user.type(screen.getByRole('textbox', { name: 'Question' }), 'What is a quality policy?')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(
      await screen.findByText('Rate limit exceeded. Maximum 10 queries per minute.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByText('What is a quality policy?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
  })
})
