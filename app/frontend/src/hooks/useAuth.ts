import { useState, useEffect, useCallback } from 'react'
import { checkAuth, extractTokenFromUrl, getToken, setToken, clearToken } from '../api'

export function useAuth() {
  const [authenticated, setAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    extractTokenFromUrl()
    checkAuth().then((ok) => {
      setAuthenticated(ok)
      setLoading(false)
    })
  }, [])

  const login = useCallback((secret: string) => {
    setToken(secret)
    checkAuth().then(setAuthenticated)
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setAuthenticated(false)
  }, [])

  return { authenticated, loading, login, logout, hasToken: !!getToken() }
}
