import { Amplify } from 'aws-amplify'
import { cognitoUserPoolsTokenProvider } from 'aws-amplify/auth/cognito'
import { sharedInMemoryStorage } from 'aws-amplify/utils'

import { appConfig, isAuthConfigured } from '../config/env'

export const configureAmplify = (): void => {
  if (!isAuthConfigured()) {
    return
  }

  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: appConfig.cognitoUserPoolId,
        userPoolClientId: appConfig.cognitoAppClientId,
      },
    },
  })

  // Tokens live in memory instead of localStorage to limit XSS exposure;
  // the trade-off is that a full page reload ends the session.
  cognitoUserPoolsTokenProvider.setKeyValueStorage(sharedInMemoryStorage)
}
