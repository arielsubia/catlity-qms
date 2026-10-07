declare global {
  interface ImportMetaEnv {
    readonly VITE_COGNITO_USER_POOL_ID?: string
    readonly VITE_COGNITO_APP_CLIENT_ID?: string
    readonly VITE_API_BASE_URL?: string
  }
}

export {}
