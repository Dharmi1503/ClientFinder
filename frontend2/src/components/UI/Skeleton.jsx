import React from 'react'
import { cn } from '../../utils/cn' // Assuming a utility exists or I'll create it

export default function Skeleton({ className = '', variant = 'rect' }) {
  const baseClasses = "animate-pulse bg-gray-200 dark:bg-gray-800"
  
  const variants = {
    rect: "rounded-xl",
    circle: "rounded-full",
    text: "rounded-md h-4 w-full"
  }

  return (
    <div 
      className={`
        ${baseClasses} 
        ${variants[variant]} 
        ${className}
      `} 
    />
  )
}
