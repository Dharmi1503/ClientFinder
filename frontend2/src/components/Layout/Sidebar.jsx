import React from 'react'
import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  Search,
  Users,
  BarChart3,
  Settings,
  UserCircle,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Brain,
  Zap,
} from 'lucide-react'

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/run-search', icon: Search, label: 'Run Search' },
  { path: '/saved-leads', icon: Users, label: 'Saved Leads' },
  { path: '/analytics', icon: BarChart3, label: 'Analytics' },
  { path: '/operations', icon: Settings, label: 'Operations' },
]

export default function Sidebar({ collapsed, setCollapsed }) {
  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 80 : 280 }}
      className="fixed left-0 top-0 h-full bg-white/70 dark:bg-gray-900/70 backdrop-blur-2xl border-r border-gray-200/50 dark:border-gray-800/50 z-30 transition-all duration-300"
    >
      <div className="flex flex-col h-full">
        {/* Logo */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200/50 dark:border-gray-800/50">
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-3"
            >
              <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-cyan-500 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-500/20">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <div className="flex flex-col">
                <span className="font-bold text-lg tracking-tight">ClientFinder</span>
                <span className="text-[10px] uppercase tracking-widest text-indigo-500 font-bold">AI Analytics</span>
              </div>
            </motion.div>
          )}
          {collapsed && (
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-cyan-500 rounded-2xl flex items-center justify-center mx-auto shadow-lg shadow-indigo-500/20">
              <Brain className="w-6 h-6 text-white" />
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-8 px-4 space-y-2">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `
                relative group flex items-center gap-3 px-4 py-3 rounded-2xl transition-all duration-300
                ${isActive 
                  ? 'bg-indigo-600/10 text-indigo-600 dark:text-indigo-400' 
                  : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800/50'
                }
                ${collapsed ? 'justify-center' : ''}
              `}
              title={collapsed ? item.label : ''}
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.div
                      layoutId="active-pill"
                      className="absolute left-0 w-1 h-6 bg-indigo-600 rounded-r-full"
                      transition={{ type: "spring", stiffness: 300, damping: 30 }}
                    />
                  )}
                  <item.icon className={`w-5 h-5 transition-transform duration-300 group-hover:scale-110 ${isActive ? 'text-indigo-600' : ''}`} />
                  {!collapsed && <span className="font-semibold text-sm">{item.label}</span>}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User Profile */}
        <div className="p-6 mt-auto">
          <div className={`p-4 rounded-2xl bg-gray-50 dark:bg-gray-800/30 border border-gray-200/50 dark:border-gray-700/30 transition-all ${collapsed ? 'p-2' : ''}`}>
            <div className={`flex items-center gap-3 ${collapsed ? 'justify-center' : ''}`}>
              <div className="w-10 h-10 bg-gradient-to-br from-indigo-400 to-cyan-400 rounded-xl flex items-center justify-center shadow-inner">
                <UserCircle className="w-7 h-7 text-white" />
              </div>
              {!collapsed && (
                <div className="flex-1 min-w-0">
                  <p className="font-bold text-sm truncate">Dharmi Mulani</p>
                  <p className="text-[10px] text-gray-500 dark:text-gray-400 truncate">Pro Plan</p>
                </div>
              )}
            </div>
            
            {!collapsed && (
              <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700/50 flex items-center justify-between">
                <button className="p-2 text-gray-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl transition-all">
                  <LogOut className="w-4 h-4" />
                </button>
                <button className="p-2 text-gray-500 hover:text-indigo-500 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 rounded-xl transition-all">
                  <Settings className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Collapse Toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-3 top-24 w-6 h-6 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-full flex items-center justify-center shadow-md hover:scale-110 transition-transform z-40"
        >
          {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
        </button>
      </div>
    </motion.aside>
  )
}