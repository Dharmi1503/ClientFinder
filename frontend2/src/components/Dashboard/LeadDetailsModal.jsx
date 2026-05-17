import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  X, 
  MessageCircle, 
  Linkedin, 
  Mail, 
  Copy, 
  Check, 
  ExternalLink,
  Target,
  Zap,
  ShieldCheck,
  TrendingUp,
  AlertCircle,
  Sparkles,
  ExternalLink as LinkIcon,
  Globe
} from 'lucide-react'

export default function LeadDetailsModal({ lead, onClose }) {
  const [copiedType, setCopiedType] = React.useState(null)

  if (!lead) return null

  const handleCopy = (text, type) => {
    navigator.clipboard.writeText(text)
    setCopiedType(type)
    setTimeout(() => setCopiedType(null), 2000)
  }

  const isPlatform = lead.lead_type === 'platform'

  const sections = isPlatform ? [
    {
      id: 'bid',
      title: 'Platform Bid Message',
      icon: Globe,
      content: lead.personalized_opener
        ? `${lead.personalized_opener}\n\n${lead.email_msg || ''}`
        : lead.email_msg,
      color: 'bg-orange-500',
      action: lead.source_url,
    },
    {
      id: 'linkedin',
      title: 'LinkedIn Message',
      icon: Linkedin,
      content: lead.linkedin_msg,
      color: 'bg-blue-600',
      action: lead.linkedin_url,
    },
  ] : [
    { 
      id: 'whatsapp', 
      title: 'WhatsApp Opener', 
      icon: MessageCircle, 
      content: lead.whatsapp_msg,
      color: 'bg-green-500',
      action: `https://wa.me/${lead.phone?.replace(/[^0-9]/g, '')}`
    },
    { 
      id: 'linkedin', 
      title: 'LinkedIn Message', 
      icon: Linkedin, 
      content: lead.linkedin_msg,
      color: 'bg-blue-600',
      action: lead.linkedin_url
    },
    { 
      id: 'email', 
      title: 'Email Template', 
      icon: Mail, 
      content: lead.email_msg,
      subject: lead.email_subject,
      color: 'bg-indigo-500',
      action: `mailto:${lead.email}?subject=${encodeURIComponent(lead.email_subject || '')}`
    }
  ]

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-gray-900/60 backdrop-blur-sm"
        />

        {/* Modal */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          className="relative w-full max-w-4xl max-h-[90vh] overflow-hidden glass rounded-3xl shadow-2xl flex flex-col"
        >
          {/* Header */}
          <div className="p-6 border-b border-gray-200/50 dark:border-gray-700/50 flex items-center justify-between bg-white/50 dark:bg-gray-800/50">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-2xl flex items-center justify-center text-white shadow-lg ${
                lead.label === 'HOT' ? 'bg-gradient-to-br from-red-500 to-orange-500' :
                lead.label === 'WARM' ? 'bg-gradient-to-br from-amber-500 to-orange-400' :
                'bg-gradient-to-br from-blue-500 to-indigo-500'
              }`}>
                <Zap className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white">{lead.company_name}</h2>
                <p className="text-gray-500 dark:text-gray-400 text-sm flex items-center gap-2">
                  {lead.industry} • {lead.city}
                  {lead.website && !isPlatform && (
                    <a href={lead.website} target="_blank" rel="noopener noreferrer" className="text-indigo-500 hover:underline flex items-center gap-0.5">
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </p>
                {isPlatform && (
                  <span className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400 rounded-full">
                    <Globe className="w-3 h-3" /> Platform Lead · {lead.source}
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl transition-colors"
            >
              <X className="w-6 h-6 text-gray-400" />
            </button>
          </div>

          {/* View Post banner for platform leads */}
          {isPlatform && lead.source_url && (
            <div className="px-6 py-3 bg-orange-50 dark:bg-orange-900/20 border-b border-orange-200/50 dark:border-orange-800/50 flex items-center justify-between">
              <span className="text-sm text-orange-700 dark:text-orange-300 font-medium">
                This lead is a live project post on {lead.source}
              </span>
              <a
                href={lead.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white text-sm font-bold rounded-xl transition-colors"
              >
                <ExternalLink className="w-4 h-4" />
                View Post
              </a>
            </div>
          )}

          <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar">
            {/* Strategy Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-2xl bg-indigo-50/50 dark:bg-indigo-900/20 border border-indigo-100/50 dark:border-indigo-800/50">
                <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400 font-semibold mb-2">
                  <Target className="w-4 h-4" />
                  <span>Pain Point</span>
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                  {lead.pain_point || "Analyzing specific business challenges..."}
                </p>
              </div>
              <div className="p-4 rounded-2xl bg-emerald-50/50 dark:bg-emerald-900/20 border border-emerald-100/50 dark:border-emerald-800/50">
                <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-semibold mb-2">
                  <TrendingUp className="w-4 h-4" />
                  <span>Buying Signals</span>
                </div>
                <ul className="text-xs text-gray-700 dark:text-gray-300 space-y-1">
                  {lead.buying_signals && lead.buying_signals.length > 0 ? (
                    lead.buying_signals.map((s, i) => <li key={i}>• {s}</li>)
                  ) : (
                    <li>• Active business presence</li>
                  )}
                </ul>
              </div>
              <div className="p-4 rounded-2xl bg-amber-50/50 dark:bg-amber-900/20 border border-amber-100/50 dark:border-amber-800/50">
                <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-semibold mb-2">
                  <ShieldCheck className="w-4 h-4" />
                  <span>Decision Maker</span>
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300">
                  {lead.decision_maker || "Owner / Founder"}
                </p>
              </div>
            </div>

            {/* AI Templates */}
            <div className="space-y-4">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-500" />
                AI Outreach Strategies
              </h3>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {sections.map((section) => (
                  <div key={section.id} className="relative group">
                    <div className="p-5 rounded-2xl bg-white/40 dark:bg-gray-900/40 border border-gray-200 dark:border-gray-800 hover:border-indigo-500/50 transition-colors">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <div className={`p-1.5 rounded-lg text-white ${section.color}`}>
                            <section.icon className="w-4 h-4" />
                          </div>
                          <span className="font-bold text-sm uppercase tracking-wider">{section.title}</span>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleCopy(section.content, section.id)}
                            className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors text-gray-400 hover:text-indigo-500"
                            title="Copy to clipboard"
                          >
                            {copiedType === section.id ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                          </button>
                          {section.action && (
                            <a
                              href={section.action}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="p-1.5 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors text-gray-400 hover:text-indigo-500"
                              title="Open app"
                            >
                              <ExternalLink className="w-4 h-4" />
                            </a>
                          )}
                        </div>
                      </div>
                      <div className="bg-gray-50/50 dark:bg-gray-950/50 p-4 rounded-xl border border-gray-100 dark:border-gray-800">
                        {section.subject && (
                          <div className="mb-2 pb-2 border-b border-gray-200 dark:border-gray-800 font-medium text-xs text-gray-500">
                            Subject: <span className="text-gray-900 dark:text-gray-200">{section.subject}</span>
                          </div>
                        )}
                        <p className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap italic">
                          "{section.content || `AI is drafting a personalized ${section.title}...`}"
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Score Reason */}
            <div className="p-4 rounded-2xl bg-indigo-500/5 border border-indigo-500/10 flex items-start gap-4">
              <AlertCircle className="w-5 h-5 text-indigo-500 shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-bold text-indigo-600 dark:text-indigo-400">AI Score Justification</h4>
                <p className="text-xs text-gray-600 dark:text-gray-400 italic mt-1">
                  {lead.hot_reason || "Based on intent signals, contact density, and local market relevance."}
                </p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}
