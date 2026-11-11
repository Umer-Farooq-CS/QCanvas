'use client'

import { useState, useEffect, useRef } from 'react'
import { Search } from '@/components/Icons';
import { Replace, X, ChevronDown, ChevronUp, Regex, WholeWord } from 'lucide-react';
import { useActiveFile, useFileStore } from '@/lib/store'
import toast from 'react-hot-toast'

interface FindReplaceProps {
  isVisible: boolean
  onClose: () => void
  mode: 'find' | 'replace'
  editorRef?: React.MutableRefObject<any>
}

export default function FindReplace({ isVisible, onClose, mode, editorRef }: FindReplaceProps) {
  const updateFileContent = useFileStore((s) => s.updateFileContent)
  const [findText, setFindText] = useState('')
  const [replaceText, setReplaceText] = useState('')
  const [matchCase, setMatchCase] = useState(false)
  const [wholeWord, setWholeWord] = useState(false)
  const [useRegex, setUseRegex] = useState(false)
  const [currentMatch, setCurrentMatch] = useState(0)
  const [totalMatches, setTotalMatches] = useState(0)
  const [isExpanded, setIsExpanded] = useState(mode === 'replace')

  const findInputRef = useRef<HTMLInputElement>(null)
  const replaceInputRef = useRef<HTMLInputElement>(null)

  const activeFile = useActiveFile()

  useEffect(() => {
    if (isVisible && findInputRef.current) {
      findInputRef.current.focus()
    }
  }, [isVisible])

  useEffect(() => {
    if (mode === 'replace') {
      setIsExpanded(true)
    } else if (mode === 'find') {
      setIsExpanded(false)
    }
  }, [mode])

  useEffect(() => {
    if (findText && activeFile) {
      findMatches()
    } else {
      setTotalMatches(0)
      setCurrentMatch(0)
    }
  }, [findText, matchCase, wholeWord, useRegex, activeFile?.content])

  const createSearchRegex = (text: string) => {
    try {
      let pattern = text
      if (!useRegex) {
        pattern = text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') // Escape special regex chars
      }
      
      if (wholeWord) {
        pattern = `\\b${pattern}\\b`
      }
      
      const flags = matchCase ? 'g' : 'gi'
      return new RegExp(pattern, flags)
    } catch (error) {
      return null
    }
  }

  const findMatches = () => {
    if (!activeFile || !findText) {
      setTotalMatches(0)
      setCurrentMatch(0)
      return
    }

    // Use Monaco editor's find functionality if available
    if (editorRef?.current) {
      const editor = editorRef.current
      const model = editor.getModel()
      if (model) {
        const matches = model.findMatches(
          findText,
          false, // searchOnlyEditableRange
          !useRegex, // isRegex
          matchCase, // matchCase
          wholeWord ? findText : null, // matchWholeWord
          false // captureMatches
        )
        setTotalMatches(matches.length)
        if (matches.length > 0) {
          setCurrentMatch(1)
          // Highlight first match
          editor.setSelection(matches[0].range)
          editor.revealRangeInCenter(matches[0].range)
        } else {
          setCurrentMatch(0)
        }
        return
      }
    }

    // Fallback to regex matching
    const regex = createSearchRegex(findText)
    if (!regex) {
      setTotalMatches(0)
      setCurrentMatch(0)
      return
    }

    const matches = Array.from(activeFile.content.matchAll(regex))
    setTotalMatches(matches.length)
    if (matches.length > 0) {
      setCurrentMatch(1)
    } else {
      setCurrentMatch(0)
    }
  }

  const findNext = () => {
    if (!editorRef?.current || !findText) {
      toast.error('No matches found')
      return
    }

    const editor = editorRef.current
    const model = editor.getModel()
    if (!model) return

    const matches = model.findMatches(
      findText,
      false,
      !useRegex,
      matchCase,
      wholeWord ? findText : null,
      false
    )

    if (matches.length > 0) {
      const next = currentMatch >= totalMatches ? 1 : currentMatch + 1
      setCurrentMatch(next)
      const matchIndex = next - 1
      if (matches[matchIndex]) {
        editor.setSelection(matches[matchIndex].range)
        editor.revealRangeInCenter(matches[matchIndex].range)
      }
    } else {
      toast.error('No matches found')
    }
  }

  const findPrevious = () => {
    if (!editorRef?.current || !findText) {
      toast.error('No matches found')
      return
    }

    const editor = editorRef.current
    const model = editor.getModel()
    if (!model) return

    const matches = model.findMatches(
      findText,
      false,
      !useRegex,
      matchCase,
      wholeWord ? findText : null,
      false
    )

    if (matches.length > 0) {
      const prev = currentMatch <= 1 ? totalMatches : currentMatch - 1
      setCurrentMatch(prev)
      const matchIndex = prev - 1
      if (matches[matchIndex]) {
        editor.setSelection(matches[matchIndex].range)
        editor.revealRangeInCenter(matches[matchIndex].range)
      }
    } else {
      toast.error('No matches found')
    }
  }

  const replaceOne = () => {
    if (!editorRef?.current || !findText || !activeFile) {
      toast.error('No text to replace')
      return
    }

    const editor = editorRef.current
    const model = editor.getModel()
    if (!model) return

    const selection = editor.getSelection()
    if (selection && !selection.isEmpty()) {
      const selectedText = model.getValueInRange(selection)
      const regex = createSearchRegex(findText)
      if (regex && regex.test(selectedText)) {
        editor.executeEdits('replace', [{
          range: selection,
          text: replaceText,
          forceMoveMarkers: true
        }])
        toast.success('Replaced 1 occurrence')
        findNext()
        return
      }
    }

    // If no selection or selection doesn't match, find first match
    const matches = model.findMatches(
      findText,
      false,
      !useRegex,
      matchCase,
      wholeWord ? findText : null,
      false
    )

    if (matches.length > 0) {
      editor.executeEdits('replace', [{
        range: matches[0].range,
        text: replaceText,
        forceMoveMarkers: true
      }])
      toast.success('Replaced 1 occurrence')
      findMatches() // Refresh match count
    } else {
      toast.error('No matches found to replace')
    }
  }

  const replaceAll = () => {
    if (!editorRef?.current || !findText || !activeFile) {
      toast.error('No text to replace')
      return
    }

    const editor = editorRef.current
    const model = editor.getModel()
    if (!model) return

    const matches = model.findMatches(
      findText,
      false,
      !useRegex,
      matchCase,
      wholeWord ? findText : null,
      false
    )

    if (matches.length > 0) {
      const edits = matches.map((match: any) => ({
        range: match.range,
        text: replaceText,
        forceMoveMarkers: true
      }))

      editor.executeEdits('replace-all', edits)
      toast.success(`Replaced ${matches.length} occurrence${matches.length > 1 ? 's' : ''}`)
      findMatches() // Refresh match count
    } else {
      toast.error('No matches found to replace')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (e.shiftKey) {
        findPrevious()
      } else {
        findNext()
      }
    } else if (e.key === 'Escape') {
      onClose()
    }
  }

  if (!isVisible) return null

  return (
    <div className="find-replace-container bg-editor-panelHigh/95 backdrop-blur-md shadow-[0_8px_24px_rgba(0,0,0,0.35)]">
      <div className="p-3 space-y-3">
        {/* Find Row */}
        <div className="flex items-center space-x-2">
          <div className="flex items-center flex-1 space-x-2">
            <Search className="w-4 h-4 text-editor-text flex-shrink-0" />
            <div className="relative flex-1">
              <input
                ref={findInputRef}
                type="text"
                value={findText}
                onChange={(e) => setFindText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Find"
                className="w-full px-3 py-1.5 bg-editor-panelLowest border border-editor-border rounded text-white placeholder-gray-400 text-sm focus-quantum"
              />
              {totalMatches > 0 && (
                <div className="absolute right-2 top-1/2 transform -translate-y-1/2 text-xs text-black dark:text-gray-400">
                  {currentMatch}/{totalMatches}
                </div>
              )}
            </div>
          </div>

          {/* Find Navigation */}
          <div className="flex items-center space-x-1">
            <button
              onClick={findPrevious}
              disabled={totalMatches === 0}
              className="p-1 hover:bg-quantum-blue-light/20 rounded disabled:opacity-50 disabled:cursor-not-allowed"
              title="Previous match (Shift+Enter)"
            >
              <ChevronUp className="w-4 h-4" />
            </button>
            <button
              onClick={findNext}
              disabled={totalMatches === 0}
              className="p-1 hover:bg-quantum-blue-light/20 rounded disabled:opacity-50 disabled:cursor-not-allowed"
              title="Next match (Enter)"
            >
              <ChevronDown className="w-4 h-4" />
            </button>
          </div>

          {/* Options */}
          <div className="flex items-center space-x-1">
            <button
              onClick={() => setMatchCase(!matchCase)}
              className={`p-1 rounded text-xs font-mono ${
                matchCase ? 'bg-editor-accent text-white' : 'hover:bg-editor-panelHigh/80'
              }`}
              title="Match Case"
            >
              Aa
            </button>
            <button
              onClick={() => setWholeWord(!wholeWord)}
              className={`p-1 rounded text-xs ${
                wholeWord ? 'bg-editor-accent text-white' : 'hover:bg-editor-panelHigh/80'
              }`}
              title="Match Whole Word"
            >
              <WholeWord className="w-3 h-3" />
            </button>
            <button
              onClick={() => setUseRegex(!useRegex)}
              className={`p-1 rounded text-xs ${
                useRegex ? 'bg-editor-accent text-white' : 'hover:bg-editor-panelHigh/80'
              }`}
              title="Use Regular Expression"
            >
              <Regex className="w-3 h-3" />
            </button>
          </div>

          {/* Toggle Replace */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 hover:bg-editor-panelHigh/80 rounded"
            title="Toggle Replace"
          >
            <Replace className="w-4 h-4" />
          </button>

          {/* Close */}
          <button
            onClick={onClose}
            className="p-1 hover:bg-editor-panelHigh/80 rounded"
            title="Close (Escape)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Replace Row */}
        {isExpanded && (
          <div className="flex items-center space-x-2">
            <div className="flex items-center flex-1 space-x-2">
              <Replace className="w-4 h-4 text-editor-text flex-shrink-0" />
              <input
                ref={replaceInputRef}
                type="text"
                value={replaceText}
                onChange={(e) => setReplaceText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Replace"
                className="flex-1 px-3 py-1.5 bg-editor-panelLowest border border-editor-border rounded text-white placeholder-gray-400 text-sm focus-quantum"
              />
            </div>

            {/* Replace Actions */}
            <div className="flex items-center space-x-1">
              <button
                onClick={replaceOne}
                disabled={totalMatches === 0}
                className="px-3 py-1 text-xs bg-editor-panelLowest border border-editor-border rounded hover:bg-editor-panelHigh disabled:opacity-50 disabled:cursor-not-allowed"
                title="Replace"
              >
                Replace
              </button>
              <button
                onClick={replaceAll}
                disabled={totalMatches === 0}
                className="px-3 py-1 text-xs bg-editor-panelLowest border border-editor-border rounded hover:bg-editor-panelHigh disabled:opacity-50 disabled:cursor-not-allowed"
                title="Replace All"
              >
                All
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
