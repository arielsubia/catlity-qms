export const appConfig = {
  cognitoUserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID ?? '',
  cognitoAppClientId: import.meta.env.VITE_COGNITO_APP_CLIENT_ID ?? '',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
}

export const isAuthConfigured = (): boolean =>
  Boolean(appConfig.cognitoUserPoolId && appConfig.cognitoAppClientId)
