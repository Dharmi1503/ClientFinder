import React, { useState, useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import ApiKeyGate from './components/Auth/ApiKeyGate'
import Dashboard from './pages/Dashboard'
import RunSearch from './pages/RunSearch'
import SavedLeads from './pages/SavedLeads'
import Analytics from './pages/Analytics'
import Operations from './pages/Operations'
import {
  clearStoredApiKey,
  getStoredApiKey,
  setStoredApiKey,
  verifyApiKey,
} from './services/api'

function App() {
  const [apiKey, setApiKeyState] = useState(() => getStoredApiKey())

  const [isDark, setIsDark] = useState(() => {
    const saved = localStorage.getItem('theme')
    return saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)
  })

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [isDark])

  useEffect(() => {
    const syncKey = () => setApiKeyState(getStoredApiKey())
    window.addEventListener('clientfinder-api-key-changed', syncKey)
    window.addEventListener('clientfinder-api-key-cleared', syncKey)
    window.addEventListener('storage', syncKey)

    return () => {
      window.removeEventListener('clientfinder-api-key-changed', syncKey)
      window.removeEventListener('clientfinder-api-key-cleared', syncKey)
      window.removeEventListener('storage', syncKey)
    }
  }, [])

  const handleSaveApiKey = async (key) => {
    await verifyApiKey(key)
    setStoredApiKey(key)
    setApiKeyState(key)
  }

  const handleClearApiKey = () => {
    clearStoredApiKey()
    setApiKeyState('')
  }

  return (
    <>
      {!apiKey ? (
        <ApiKeyGate
          apiKey={apiKey}
          onSave={handleSaveApiKey}
          onClear={handleClearApiKey}
        />
      ) : (
        <Layout isDark={isDark} setIsDark={setIsDark} onLogout={handleClearApiKey}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/run-search" element={<RunSearch />} />
            <Route path="/saved-leads" element={<SavedLeads />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/operations" element={<Operations />} />
          </Routes>
        </Layout>
      )}
    </>
  )
}

export default App