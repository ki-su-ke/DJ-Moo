import { apiRequest } from '../../shared/api'
import { authenticatedRequest } from './auth'

export type Membership = {
  id: string
  organization: { id: string; name: string; slug: string }
  roles: Array<{ id: string; name: string }>
  is_org_admin: boolean
  scope_type: string
}

export type UserProfile = {
  id: string
  email: string
  is_active: boolean
  created_at: string
  updated_at: string
  memberships: Membership[]
}

export type OrganizationMember = {
  id: string
  user_id: string
  email: string
  is_org_admin: boolean
}

type MessageResponse = { message: string }

export function requestRegistration(email: string) {
  return apiRequest<MessageResponse>('/api/v1/auth/register/', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

export function getProfile() {
  return authenticatedRequest<UserProfile>('/api/v1/auth/me/')
}

/** DELETE 成功後は 204 を null として受け取る。 */
export function deleteMyAccount() {
  return authenticatedRequest<null>('/api/v1/auth/me/delete/', {
    method: 'DELETE',
    body: JSON.stringify({ confirmation: 'DELETE' }),
  })
}

/** 組織 Admin 用の有効メンバー一覧を取得する。 */
export function getOrganizationMembers(organizationSlug: string) {
  return authenticatedRequest<{ members: OrganizationMember[] }>(
    `/api/v1/${encodeURIComponent(organizationSlug)}/members/`,
  )
}

/** アカウントではなく、指定組織の Membership だけを削除する。 */
export function removeOrganizationMember(organizationSlug: string, membershipId: string) {
  return authenticatedRequest<null>(
    `/api/v1/${encodeURIComponent(organizationSlug)}/members/${encodeURIComponent(membershipId)}/`,
    { method: 'DELETE' },
  )
}

export function requestPasswordChange() {
  return authenticatedRequest<MessageResponse>('/api/v1/auth/change-password-request/', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function requestEmailChange(newEmail: string) {
  return authenticatedRequest<MessageResponse>('/api/v1/auth/change-email-request/', {
    method: 'POST',
    body: JSON.stringify({ new_email: newEmail }),
  })
}