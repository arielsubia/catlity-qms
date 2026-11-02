import { Alert, Button, Typography, Upload, type UploadFile, type UploadProps } from 'antd'
import { useEffect, useState } from 'react'

import {
  MAX_EVIDENCE_BYTES,
  contentTypeFor,
  listFindingEvidence,
  requestDownloadUrl,
  uploadAndLink,
  type FindingEvidence,
} from '../api/evidence-api'
import { ApiError } from '../api/http'

interface FindingEvidencePanelProps {
  findingId: string
}

const messageOf = (err: unknown, fallback: string): string =>
  err instanceof ApiError ? err.message : fallback

const isImage = (contentType: string): boolean => contentType.startsWith('image/')

export const FindingEvidencePanel = ({ findingId }: FindingEvidencePanelProps) => {
  const [items, setItems] = useState<FindingEvidence[]>([])
  const [previews, setPreviews] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState<UploadFile[]>([])
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    void listFindingEvidence(findingId)
      .then((result) => {
        if (active) {
          setItems(result.items)
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(messageOf(err, 'Could not load evidence.'))
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
  }, [findingId])

  useEffect(() => {
    let active = true
    const images = items.filter((item) => isImage(item.content_type))
    if (images.length === 0) {
      return
    }
    void Promise.all(
      images.map(async (item) => {
        const ticket = await requestDownloadUrl(item.evidence_id)
        return [item.evidence_id, ticket.download_url] as const
      }),
    )
      .then((pairs) => {
        if (active) {
          setPreviews(Object.fromEntries(pairs))
        }
      })
      .catch((err: unknown) => {
        if (active) {
          setError(messageOf(err, 'Could not load an image preview.'))
        }
      })
    return () => {
      active = false
    }
  }, [items])

  const beforeUpload = (file: File) => {
    if (contentTypeFor(file) === null) {
      setError('File type must be PDF, PNG, JPG, or DOCX.')
      return Upload.LIST_IGNORE
    }
    if (file.size < 1 || file.size > MAX_EVIDENCE_BYTES) {
      setError('File size must be between 1 byte and 25 MB.')
      return Upload.LIST_IGNORE
    }
    setError(null)
    return true
  }

  const uploadFile: UploadProps['customRequest'] = (options) => {
    if (!(options.file instanceof File)) {
      options.onError?.(new Error('Choose a file to upload.'))
      return
    }
    const file = options.file
    setError(null)
    void uploadAndLink(findingId, file, (percent) => {
      options.onProgress?.({ percent })
    })
      .then((linked) => {
        options.onSuccess?.(linked)
        setItems((current) => [...current, linked])
      })
      .catch((err: unknown) => {
        const message = messageOf(err, 'Could not upload the file.')
        options.onError?.(err instanceof Error ? err : new Error(message))
        setError(message)
      })
  }

  const download = async (evidenceId: string) => {
    setError(null)
    setDownloadingId(evidenceId)
    try {
      const ticket = await requestDownloadUrl(evidenceId)
      window.open(ticket.download_url, '_blank', 'noopener,noreferrer')
    } catch (err) {
      setError(messageOf(err, 'Could not download the file.'))
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <section className="evidence-panel">
      <Typography.Title level={5}>Evidence</Typography.Title>
      <Upload.Dragger
        accept=".pdf,.png,.jpg,.jpeg,.docx"
        multiple
        listType="picture"
        fileList={uploading}
        beforeUpload={beforeUpload}
        customRequest={uploadFile}
        showUploadList={{ showRemoveIcon: false }}
        onChange={({ fileList }) => {
          setUploading(fileList.filter((file) => file.status === 'uploading'))
        }}
      >
        <p>Drop evidence here, or click to choose a file</p>
        <p>PDF, PNG, JPG, or DOCX. Maximum 25 MB.</p>
      </Upload.Dragger>
      {error && <Alert type="error" showIcon className="auth-alert" title={error} />}
      {loading && <Typography.Paragraph>Loading evidence...</Typography.Paragraph>}
      {!loading && !error && items.length === 0 && (
        <Typography.Paragraph>No files linked to this finding yet.</Typography.Paragraph>
      )}
      {items.length > 0 && (
        <ul className="evidence-gallery">
          {items.map((item) => (
            <li key={item.id} className="evidence-item">
              {isImage(item.content_type) && previews[item.evidence_id] && (
                <img
                  className="evidence-preview"
                  src={previews[item.evidence_id]}
                  alt={item.file_name}
                />
              )}
              <span className="evidence-file-name">{item.file_name}</span>
              <Button
                onClick={() => void download(item.evidence_id)}
                loading={downloadingId === item.evidence_id}
              >
                {`Download ${item.file_name}`}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
