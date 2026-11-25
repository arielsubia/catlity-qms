import { apiRequest } from './http'

export interface EmbedUrl {
  embed_url: string
  expires_at: string
}

export const getEmbedUrl = (): Promise<EmbedUrl> =>
  apiRequest<EmbedUrl>('/api/v1/quicksight/embed-url')
