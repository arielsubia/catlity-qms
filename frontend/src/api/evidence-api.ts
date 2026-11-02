import { ApiError, apiRequest } from './http'

export const MAX_EVIDENCE_BYTES = 25 * 1024 * 1024

const EXTENSION_TYPES: Record<string, string> = {
  pdf: 'application/pdf',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}

export interface UploadUrlResponse {
  evidence_id: string
  upload_url: string
  expires_in: number
  headers: Record<string, string>
  s3_key: string
}

export interface DownloadUrlResponse {
  evidence_id: string
  download_url: string
  expires_in: number
  file_name: string
  content_type: string
}

export interface FindingEvidence {
  id: string
  tenant_id: string
  finding_id: string
  evidence_id: string
  file_name: string
  content_type: string
  file_size: number
  s3_key: string
  status: string
  uploaded_by: string
  uploaded_at: string | null
  linked_by: string
  created_at: string
}

export interface FindingEvidenceList {
  items: FindingEvidence[]
}

export const contentTypeFor = (file: Pick<File, 'name' | 'type'>): string | null => {
  const extension = file.name.split('.').pop()?.toLowerCase() ?? ''
  const mapped = EXTENSION_TYPES[extension]
  if (!mapped) {
    return null
  }
  if (file.type === '' || file.type === 'application/octet-stream' || file.type === mapped) {
    return mapped
  }
  if (file.type === 'image/jpg' && mapped === 'image/jpeg') {
    return mapped
  }
  return null
}

export const requestUploadUrl = (
  fileName: string,
  contentType: string,
  fileSize: number,
): Promise<UploadUrlResponse> =>
  apiRequest<UploadUrlResponse>('/api/v1/evidence/upload-url', {
    method: 'POST',
    body: JSON.stringify({
      file_name: fileName,
      content_type: contentType,
      file_size: fileSize,
    }),
  })

export const confirmUpload = (evidenceId: string): Promise<void> =>
  apiRequest<unknown>(`/api/v1/evidence/${evidenceId}/confirm`, { method: 'POST' }).then(
    () => undefined,
  )

export const linkFindingEvidence = (
  findingId: string,
  evidenceId: string,
): Promise<FindingEvidence> =>
  apiRequest<FindingEvidence>(`/api/v1/findings/${findingId}/evidence`, {
    method: 'POST',
    body: JSON.stringify({ evidence_id: evidenceId }),
  })

export const listFindingEvidence = (findingId: string): Promise<FindingEvidenceList> =>
  apiRequest<FindingEvidenceList>(`/api/v1/findings/${findingId}/evidence`)

export const requestDownloadUrl = (evidenceId: string): Promise<DownloadUrlResponse> =>
  apiRequest<DownloadUrlResponse>(`/api/v1/evidence/${evidenceId}/download-url`)

// The browser sets Content-Length from the body and forbids setting it in script.
// The signed length still matches the file size.
const skipHeader = (name: string): boolean => name.toLowerCase() === 'content-length'

export const putEvidenceFile = (
  url: string,
  file: Blob,
  headers: Record<string, string>,
  onProgress: (percent: number) => void,
): Promise<void> =>
  new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', url)
    for (const [name, value] of Object.entries(headers)) {
      if (!skipHeader(name)) {
        xhr.setRequestHeader(name, value)
      }
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve()
        return
      }
      reject(new ApiError('Upload to storage failed.', xhr.status))
    }
    xhr.onerror = () => {
      reject(new ApiError('Could not reach storage.', 0))
    }
    xhr.send(file)
  })

export const uploadAndLink = async (
  findingId: string,
  file: File,
  onProgress: (percent: number) => void,
): Promise<FindingEvidence> => {
  const contentType = contentTypeFor(file)
  if (contentType === null) {
    throw new ApiError('File type must be PDF, PNG, JPG, or DOCX.', 422)
  }
  if (file.size < 1 || file.size > MAX_EVIDENCE_BYTES) {
    throw new ApiError('File size must be between 1 byte and 25 MB.', 422)
  }
  const ticket = await requestUploadUrl(file.name, contentType, file.size)
  await putEvidenceFile(ticket.upload_url, file, ticket.headers, onProgress)
  await confirmUpload(ticket.evidence_id)
  return linkFindingEvidence(findingId, ticket.evidence_id)
}
