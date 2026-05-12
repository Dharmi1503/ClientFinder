import React from 'react'
import { cn } from '../../utils/cn'

export default function Badge({ children, variant = 'default', className = '' }) {
  const variants = {
    default: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
    primary: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400",
    success: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
    warning: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    error: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    hot: "bg-red-500 text-white shadow-lg shadow-red-500/30 animate-pulse-slow",
  }

  return (
    <span className={cn(
      "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium transition-all duration-300",
      variants[variant],
      className
    )}>
      {variant === 'hot' && (
        <span className="mr-1.5 flex h-1.5 w-1.5 items-center">
          <span className="absolute inline-flex h-1.5 w-1.5 animate-ping rounded-full bg-white opacity-75"></span>
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-white"></span>
        </span>
      )}
      {children}
    </span>
  )
}
