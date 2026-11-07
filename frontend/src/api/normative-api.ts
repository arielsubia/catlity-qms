import { apiRequest } from './http'

export interface NormativeReference {
  document: string
  section: string
}

export interface NormativeQueryResponse {
  answer: string
  references: NormativeReference[]
}

export const queryNormative = (question: string): Promise<NormativeQueryResponse> =>
  apiRequest<NormativeQueryResponse>('/api/v1/ai/normative/query', {
    method: 'POST',
    body: JSON.stringify({ question }),
  })
