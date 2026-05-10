import React, { useState, useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import Dashboard from './pages/Dashboard'
import RunSearch from './pages/RunSearch'
import SavedLeads from './pages/SavedLeads'
import Analytics from './pages/Analytics'
import Operations from './pages/Operations'

function App() {
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

  return (
    <Layout isDark={isDark} setIsDark={setIsDark}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/run-search" element={<RunSearch />} />
        <Route path="/saved-leads" element={<SavedLeads />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/operations" element={<Operations />} />
      </Routes>
    </Layout>
  )
}

export default App