import React, { useState } from 'react'
import Sidebar from './Sidebar'
import Header from './Header'
import { motion, AnimatePresence } from 'framer-motion'

export default function Layout({ children, isDark, setIsDark }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 relative">
      {/* Animated background blobs */}
      <div className="blob-animation top-20 -left-20" />
      <div className="blob-animation bottom-20 -right-20" style={{ animationDelay: '-5s' }} />
      
      <Sidebar collapsed={sidebarCollapsed} setCollapsed={setSidebarCollapsed} />
      
      <div className={`transition-all duration-300 ${sidebarCollapsed ? 'ml-20' : 'ml-64'}`}>
        <Header isDark={isDark} setIsDark={setIsDark} />
        
        <AnimatePresence mode="wait">
          <motion.main
            key={location.pathname}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
            className="p-6 md:p-8"
          >
            {children}
          </motion.main>
        </AnimatePresence>
      </div>
    </div>
  )
}