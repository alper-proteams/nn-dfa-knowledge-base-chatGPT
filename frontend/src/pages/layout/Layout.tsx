import { useContext, useEffect, useMemo, useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { Dialog, Stack, TextField } from '@fluentui/react'
import { CopyRegular } from '@fluentui/react-icons'

import { CosmosDBStatus, getUserInfo, UserInfo } from '../../api'
import NNLogoWhite from '../../assets/nn_logo_white.png'
import { HistoryButton, ShareButton } from '../../components/common/Button'
import { AppStateContext } from '../../state/AppProvider'

import styles from './Layout.module.css'

type NormalizedClaim = {
  type: string
  value: string
}

const normalizeClaims = (claims: any[] | undefined): NormalizedClaim[] => {
  if (!Array.isArray(claims)) {
    return []
  }

  return claims
    .map(claim => {
      if (!claim || typeof claim !== 'object') {
        return null
      }
      const type = (claim.typ ?? claim.type ?? '').toString().trim()
      const value = (claim.val ?? claim.value ?? '').toString().trim()
      if (!type || !value) {
        return null
      }
      return { type, value }
    })
    .filter((claim): claim is NormalizedClaim => !!claim)
}

const claimMatches = (claimType: string, candidate: string) => {
  const normalizedType = claimType.toLowerCase()
  const normalizedCandidate = candidate.toLowerCase()
  return (
    normalizedType === normalizedCandidate ||
    normalizedType.endsWith(`/${normalizedCandidate}`) ||
    normalizedType.endsWith(`:${normalizedCandidate}`)
  )
}

const findClaimValue = (claims: NormalizedClaim[], candidates: string[]) => {
  for (const candidate of candidates) {
    const match = claims.find(claim => claimMatches(claim.type, candidate))
    if (match?.value) {
      return match.value
    }
  }
  return null
}

const buildUserLabel = (userInfo?: UserInfo | null) => {
  const claims = normalizeClaims(userInfo?.user_claims)
  if (!claims.length) {
    return null
  }

  const givenName = findClaimValue(claims, ['given_name', 'givenname'])
  const familyName = findClaimValue(claims, ['family_name', 'familyname', 'surname', 'lastname', 'last_name'])
  const fullNameFromParts = [givenName, familyName].filter(Boolean).join(' ').trim()
  const fullName = fullNameFromParts || findClaimValue(claims, ['name', 'displayname'])

  const email = findClaimValue(claims, [
    'email',
    'emailaddress',
    'emails',
    'preferred_username',
    'upn'
  ])

  if (fullName && email && fullName.toLowerCase() !== email.toLowerCase()) {
    return `${fullName} | ${email}`
  }

  return fullName || email || null
}

const Layout = () => {
  const [isSharePanelOpen, setIsSharePanelOpen] = useState<boolean>(false)
  const [copyClicked, setCopyClicked] = useState<boolean>(false)
  const [copyText, setCopyText] = useState<string>('Copy URL')
  const [shareLabel, setShareLabel] = useState<string | undefined>('Share')
  const [hideHistoryLabel, setHideHistoryLabel] = useState<string>('Hide chat history')
  const [showHistoryLabel, setShowHistoryLabel] = useState<string>('Show chat history')
  const [logo, setLogo] = useState('')
  const [userLabel, setUserLabel] = useState<string | null>(null)
  const appStateContext = useContext(AppStateContext)
  const ui = appStateContext?.state.frontendSettings?.ui
  const authEnabledSetting = appStateContext?.state.frontendSettings?.auth_enabled
  const isAuthEnabled = useMemo(
    () => authEnabledSetting === true || authEnabledSetting === 'true',
    [authEnabledSetting]
  )

  const handleShareClick = () => {
    setIsSharePanelOpen(true)
  }

  const handleSharePanelDismiss = () => {
    setIsSharePanelOpen(false)
    setCopyClicked(false)
    setCopyText('Copy URL')
  }

  const handleCopyClick = () => {
    navigator.clipboard.writeText(window.location.href)
    setCopyClicked(true)
  }

  const handleHistoryClick = () => {
    appStateContext?.dispatch({ type: 'TOGGLE_CHAT_HISTORY' })
  }

  useEffect(() => {
    if (!appStateContext?.state.isLoading) {
      setLogo(ui?.logo || NNLogoWhite)
    }
  }, [appStateContext?.state.isLoading])

  useEffect(() => {
    const loadUserLabel = async () => {
      if (!isAuthEnabled) {
        setUserLabel(null)
        return
      }

      try {
        const userInfoList = await getUserInfo()
        const label = buildUserLabel(userInfoList?.[0])
        setUserLabel(label)
      } catch (error) {
        console.error('Failed to load user info.', error)
        setUserLabel(null)
      }
    }

    loadUserLabel()
  }, [isAuthEnabled])

  useEffect(() => {
    if (copyClicked) {
      setCopyText('Copied URL')
    }
  }, [copyClicked])

  useEffect(() => { }, [appStateContext?.state.isCosmosDBAvailable.status])

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 480) {
        setShareLabel(undefined)
        setHideHistoryLabel('Hide history')
        setShowHistoryLabel('Show history')
      } else {
        setShareLabel('Share')
        setHideHistoryLabel('Hide chat history')
        setShowHistoryLabel('Show chat history')
      }
    }

    window.addEventListener('resize', handleResize)
    handleResize()

    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <div className={styles.layout}>
      <header className={styles.header} role={'banner'}>
        <Stack horizontal verticalAlign="center" horizontalAlign="space-between">
          <Stack horizontal verticalAlign="center">
            <img src={logo} className={styles.headerIcon} aria-hidden="true" alt="" />
            <Link to="/" className={styles.headerTitleContainer}>
              <h1 className={styles.headerTitle}>{ui?.title}</h1>
            </Link>
          </Stack>
          <Stack horizontal tokens={{ childrenGap: 8 }} className={styles.shareButtonContainer}>
            {userLabel && (
              <div className={styles.userInfo} title={userLabel} aria-label={`Signed in as ${userLabel}`}>
                <span className={styles.userInfoText}>{userLabel}</span>
              </div>
            )}
            {appStateContext?.state.isCosmosDBAvailable?.status !== CosmosDBStatus.NotConfigured && ui?.show_chat_history_button !== false && (
              <HistoryButton
                onClick={handleHistoryClick}
                text={appStateContext?.state?.isChatHistoryOpen ? hideHistoryLabel : showHistoryLabel}
              />
            )}
            {ui?.show_share_button && <ShareButton onClick={handleShareClick} text={shareLabel} />}
          </Stack>
        </Stack>
      </header>
      <Outlet />
      <Dialog
        onDismiss={handleSharePanelDismiss}
        hidden={!isSharePanelOpen}
        styles={{
          main: [
            {
              selectors: {
                ['@media (min-width: 480px)']: {
                  maxWidth: '600px',
                  background: '#FFFFFF',
                  boxShadow: '0px 14px 28.8px rgba(0, 0, 0, 0.24), 0px 0px 8px rgba(0, 0, 0, 0.2)',
                  borderRadius: '8px',
                  maxHeight: '200px',
                  minHeight: '100px'
                }
              }
            }
          ]
        }}
        dialogContentProps={{
          title: 'Share the web app',
          showCloseButton: true
        }}>
        <Stack horizontal verticalAlign="center" style={{ gap: '8px' }}>
          <TextField className={styles.urlTextBox} defaultValue={window.location.href} readOnly />
          <div
            className={styles.copyButtonContainer}
            role="button"
            tabIndex={0}
            aria-label="Copy"
            onClick={handleCopyClick}
            onKeyDown={e => (e.key === 'Enter' || e.key === ' ' ? handleCopyClick() : null)}>
            <CopyRegular className={styles.copyButton} />
            <span className={styles.copyButtonText}>{copyText}</span>
          </div>
        </Stack>
      </Dialog>
    </div>
  )
}

export default Layout
