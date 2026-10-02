import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMe, login as apiLogin, logout as apiLogout } from '../api/auth'
import type { CurrentUser } from '../types'

export function useCurrentUser() {
  const query = useQuery({
    queryKey: ['me'],
    queryFn: fetchMe,
    staleTime: 60_000,
  })
  return {
    user: query.data?.user ?? null,
    isLoading: query.isLoading,
  }
}

export function useAuthActions() {
  const queryClient = useQueryClient()

  async function login(username: string, password: string, remember: boolean) {
    const result = await apiLogin(username, password, remember)
    if (result.mfa_required) {
      return result
    }
    queryClient.setQueryData(['me'], { user: result.user })
    return result
  }

  function completeMfaLogin(user: CurrentUser) {
    queryClient.setQueryData(['me'], { user })
  }

  async function logout() {
    await apiLogout()
    queryClient.setQueryData(['me'], { user: null })
    queryClient.clear()
  }

  return { login, logout, completeMfaLogin }
}
