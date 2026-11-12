'use client'

import { useState } from 'react'
import { Upload, File, AlertCircle, Zap } from '@/components/Icons';
import { Code } from '@/components/Icons';
import { X, CheckCircle, ArrowLeft, ArrowRight, Info } from 'lucide-react';
import toast from 'react-hot-toast';

interface AddNewLanguageProps {
  isOpen: boolean
  onClose: () => void
}

interface FormData {
  languageName: string
  converterFile: File | null
}

export default function AddNewLanguage({ isOpen, onClose }: AddNewLanguageProps) {
  const [currentStep, setCurrentStep] = useState(1)
  const [formData, setFormData] = useState<FormData>({
    languageName: '',
    converterFile: null
  })
  const [isDragOver, setIsDragOver] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)

  const resetForm = () => {
    setCurrentStep(1)
    setFormData({ languageName: '', converterFile: null })
    setIsSubmitted(false)
    setIsDragOver(false)
  }

  const handleClose = () => {
    resetForm()
    onClose()
  }

  const handleLanguageNameSubmit = () => {
    if (!formData.languageName.trim()) {
      toast.error('Please enter a language name')
      return
    }
    if (formData.languageName.length < 2) {
      toast.error('Language name must be at least 2 characters')
      return
    }
    setCurrentStep(2)
  }

  const handleFileUpload = (file: File) => {
    // Validate file type
    if (!file.name.endsWith('.py')) {
      toast.error('Please upload a Python (.py) file')
      return
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      toast.error('File size must be less than 5MB')
      return
    }

    setFormData(prev => ({ ...prev, converterFile: file }))
    toast.success('Converter file uploaded successfully')
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      handleFileUpload(files[0])
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      handleFileUpload(files[0])
    }
  }

  const handleSubmit = async () => {
    if (!formData.converterFile) {
      toast.error('Please upload a converter file')
      return
    }

    // Simulate submission
    toast.loading('Submitting request...', { duration: 2000 })
    
    setTimeout(() => {
      setIsSubmitted(true)
      toast.success('Request submitted successfully!')
    }, 2000)
  }

  const converterRules = [
    {
      title: "File Structure",
      items: [
        "Must be a Python (.py) file",
        "Should follow naming convention: `{language}_to_qasm.py`",
        "File size should not exceed 5MB"
      ]
    },
    {
      title: "Required Class",
      items: [
        "Main converter class: `{Language}ToQASM3Converter`",
        "Example: `CircuitLanguageToQASM3Converter`",
        "Must inherit from base converter if available"
      ]
    },
    {
      title: "Required Methods",
      items: [
        "`convert(source_code: str) -> ConversionResult`",
        "`_execute_{language}_source(source: str)` - Parse and execute source",
        "`_analyze_{language}_circuit(circuit)` - Extract circuit statistics",
        "`_convert_to_qasm3(circuit) -> str` - Convert to OpenQASM 3.0"
      ]
    },
    {
      title: "Global Function",
      items: [
        "Must include: `convert_{language}_to_qasm3(source: str) -> ConversionResult`",
        "This function should create converter instance and call convert method",
        "Should handle all exceptions and return proper error messages"
      ]
    },
    {
      title: "Expected Input",
      items: [
        "Source code must define a `get_circuit()` function",
        "Function should return a valid circuit object for your framework",
        "Support fallback patterns for circuit detection"
      ]
    },
    {
      title: "Dependencies",
      items: [
        "Import your quantum framework (e.g., `import myframework`)",
        "Import: `from quantum_converters.base.ConversionResult import ConversionResult, ConversionStats`",
        "Handle import errors gracefully with helpful error messages"
      ]
    }
  ]

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
      <div className="quantum-glass-dark rounded-2xl max-w-5xl w-full max-h-[90vh] overflow-y-auto backdrop-blur-xl border border-white/20 shadow-2xl">
        
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-quantum-blue-dark/90 to-quantum-purple-dark/90 backdrop-blur-xl border-b border-white/10 p-6 rounded-t-2xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="p-2 bg-quantum-blue-light/20 rounded-lg">
                <Zap className="w-6 h-6 text-quantum-blue-light" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white">Add New Quantum Language</h2>
                <p className="text-quantum-blue-light">Extend Q-Canvas with your quantum framework</p>
              </div>
            </div>
            <button
              onClick={handleClose}
              className="p-2 hover:bg-white/10 rounded-lg transition-colors"
            >
              <X className="w-6 h-6 text-white" />
            </button>
          </div>

          {/* Progress Steps */}
          <div className="flex items-center space-x-4 mt-6">
            {[1, 2, 3].map((step) => (
              <div key={step} className="flex items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                  currentStep >= step 
                    ? 'bg-quantum-blue-light text-white' 
                    : currentStep === step && !isSubmitted
                    ? 'bg-white/20 text-white border-2 border-quantum-blue-light'
                    : 'bg-white/10 text-black dark:text-gray-400'
                }`}>
                  {isSubmitted && step === 3 ? (
                    <CheckCircle className="w-5 h-5" />
                  ) : (
                    step
                  )}
                </div>
                {step < 3 && (
                  <div className={`w-12 h-0.5 ml-2 ${
                    currentStep > step ? 'bg-quantum-blue-light' : 'bg-white/20'
                  }`} />
                )}
              </div>
            ))}
          </div>
          
          <div className="flex justify-between mt-2 text-sm">
            <span className={currentStep >= 1 ? 'text-quantum-blue-light' : 'text-black dark:text-gray-400'}>
              Language Details
            </span>
            <span className={currentStep >= 2 ? 'text-quantum-blue-light' : 'text-black dark:text-gray-400'}>
              Upload Converter
            </span>
            <span className={currentStep >= 3 || isSubmitted ? 'text-quantum-blue-light' : 'text-black dark:text-gray-400'}>
              Review & Submit
            </span>
          </div>
        </div>

        <div className="flex">
          {/* Main Content */}
          <div className="flex-1 p-6">
            {!isSubmitted ? (
              <>
                {/* Step 1: Language Name */}
                {currentStep === 1 && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-xl font-semibold text-white mb-2">Language Information</h3>
                      <p className="text-black dark:text-gray-300 text-sm">
                        Tell us about the quantum programming language you&apos;d like to add to Q-Canvas.
                      </p>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <label htmlFor="languageName" className="block text-sm font-medium text-white mb-2">
                          Language Name *
                        </label>
                        <input
                          id="languageName"
                          type="text"
                          value={formData.languageName}
                          onChange={(e) => setFormData(prev => ({ ...prev, languageName: e.target.value }))}
                          onKeyDown={(e) => e.key === 'Enter' && handleLanguageNameSubmit()}
                          placeholder="e.g., MyQuantumFramework, QuantumToolkit, etc."
                          className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-quantum-blue-light focus:border-transparent transition-all"
                          autoFocus
                        />
                        <p className="text-xs text-black dark:text-gray-400 mt-1">
                          This will be used to identify your language in the converter system
                        </p>
                      </div>

                      <div className="flex items-center space-x-2 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                        <Info className="w-5 h-5 text-blue-400 flex-shrink-0" />
                        <p className="text-sm text-blue-200">
                          Make sure your language name is descriptive and follows naming conventions. 
                          This will be displayed to users when selecting conversion options.
                        </p>
                      </div>
                    </div>

                    <div className="flex justify-end">
                      <button
                        onClick={handleLanguageNameSubmit}
                        disabled={!formData.languageName.trim()}
                        className="flex items-center space-x-2 px-6 py-3 bg-quantum-blue-light hover:bg-quantum-blue-dark disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                      >
                        <span>Next</span>
                        <ArrowRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}

                {/* Step 2: File Upload */}
                {currentStep === 2 && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-xl font-semibold text-white mb-2">Upload Converter File</h3>
                      <p className="text-black dark:text-gray-300 text-sm">
                        Upload your Python converter file that translates {formData.languageName} to OpenQASM 3.0.
                      </p>
                    </div>

                    {/* File Upload Area */}
                    <div
                      className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-all ${
                        isDragOver
                          ? 'border-quantum-blue-light bg-quantum-blue-light/10'
                          : formData.converterFile
                          ? 'border-green-500 bg-green-500/10'
                          : 'border-white/30 hover:border-white/50'
                      }`}
                      onDrop={handleDrop}
                      onDragOver={(e) => {
                        e.preventDefault()
                        setIsDragOver(true)
                      }}
                      onDragLeave={() => setIsDragOver(false)}
                    >
                      <input
                        type="file"
                        accept=".py"
                        onChange={handleFileSelect}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      />
                      
                      {formData.converterFile ? (
                        <div className="space-y-3">
                          <CheckCircle className="w-12 h-12 text-green-400 mx-auto" />
                          <div>
                            <p className="text-white font-medium">{formData.converterFile.name}</p>
                            <p className="text-sm text-black dark:text-gray-400">
                              {(formData.converterFile.size / 1024).toFixed(1)} KB
                            </p>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              setFormData(prev => ({ ...prev, converterFile: null }))
                            }}
                            className="text-sm text-red-400 hover:text-red-300"
                          >
                            Remove file
                          </button>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          <Upload className="w-12 h-12 text-black dark:text-gray-400 mx-auto" />
                          <div>
                            <p className="text-white font-medium">
                              Drop your converter file here or click to browse
                            </p>
                            <p className="text-sm text-black dark:text-gray-400">
                              Python (.py) files only, max 5MB
                            </p>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="flex justify-between">
                      <button
                        onClick={() => setCurrentStep(1)}
                        className="flex items-center space-x-2 px-6 py-3 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                      >
                        <ArrowLeft className="w-4 h-4" />
                        <span>Back</span>
                      </button>
                      <button
                        onClick={() => setCurrentStep(3)}
                        disabled={!formData.converterFile}
                        className="flex items-center space-x-2 px-6 py-3 bg-quantum-blue-light hover:bg-quantum-blue-dark disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
                      >
                        <span>Review</span>
                        <ArrowRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}

                {/* Step 3: Review & Submit */}
                {currentStep === 3 && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-xl font-semibold text-white mb-2">Review Your Submission</h3>
                      <p className="text-black dark:text-gray-300 text-sm">
                        Please review the information before submitting your language addition request.
                      </p>
                    </div>

                    <div className="space-y-4">
                      <div className="p-4 bg-white/5 border border-white/20 rounded-lg">
                        <h4 className="font-medium text-white mb-3">Submission Summary</h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-black dark:text-gray-300">Language Name:</span>
                            <span className="text-white font-medium">{formData.languageName}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-black dark:text-gray-300">Converter File:</span>
                            <span className="text-white font-medium">{formData.converterFile?.name}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-black dark:text-gray-300">File Size:</span>
                            <span className="text-white">
                              {formData.converterFile ? (formData.converterFile.size / 1024).toFixed(1) + ' KB' : 'N/A'}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                        <div className="flex items-center space-x-2 mb-2">
                          <AlertCircle className="w-5 h-5 text-yellow-400" />
                          <h4 className="font-medium text-yellow-200">Before You Submit</h4>
                        </div>
                        <ul className="text-sm text-yellow-100 space-y-1">
                          <li>• Ensure your converter follows all the required patterns shown in the rules</li>
                          <li>• Test your converter locally before submitting</li>
                          <li>• Make sure all dependencies are properly handled</li>
                          <li>• Verify the global function name follows the convention</li>
                        </ul>
                      </div>
                    </div>

                    <div className="flex justify-between">
                      <button
                        onClick={() => setCurrentStep(2)}
                        className="flex items-center space-x-2 px-6 py-3 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                      >
                        <ArrowLeft className="w-4 h-4" />
                        <span>Back</span>
                      </button>
                      <button
                        onClick={handleSubmit}
                        className="flex items-center space-x-2 px-8 py-3 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 rounded-lg transition-all transform hover:scale-105"
                      >
                        <CheckCircle className="w-5 h-5" />
                        <span>Submit Request</span>
                      </button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              /* Success State */
              <div className="text-center py-12 space-y-6">
                <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto">
                  <CheckCircle className="w-12 h-12 text-green-400" />
                </div>
                <div>
                  <h3 className="text-2xl font-bold text-white mb-2">Request Submitted Successfully!</h3>
                  <p className="text-black dark:text-gray-300 max-w-md mx-auto">
                    Your {formData.languageName} converter has been submitted to our administrators for review.
                    You&apos;ll be notified once it&apos;s been processed.
                  </p>
                </div>
                <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg max-w-md mx-auto">
                  <h4 className="font-medium text-blue-200 mb-2">What happens next?</h4>
                  <ul className="text-sm text-blue-100 text-left space-y-1">
                    <li>• Our team will review your converter code</li>
                    <li>• We&apos;ll test it against our quality standards</li>
                    <li>• You&apos;ll receive feedback within 3-5 business days</li>
                    <li>• Once approved, it will be integrated into Q-Canvas</li>
                  </ul>
                </div>
                <button
                  onClick={handleClose}
                  className="px-8 py-3 bg-quantum-blue-light hover:bg-quantum-blue-dark rounded-lg transition-colors"
                >
                  Close
                </button>
              </div>
            )}
          </div>

          {/* Rules Sidebar */}
          {!isSubmitted && (
            <div className="w-96 border-l border-white/10 p-6 bg-gradient-to-b from-white/5 to-transparent">
              <div className="sticky top-6">
                <div className="flex items-center space-x-2 mb-4">
                  <File className="w-5 h-5 text-quantum-blue-light" />
                  <h3 className="font-semibold text-white">Converter Requirements</h3>
                </div>
                
                <div className="space-y-4 max-h-[60vh] overflow-y-auto">
                  {converterRules.map((section, index) => (
                    <div key={index} className="space-y-2">
                      <h4 className="text-sm font-medium text-quantum-blue-light">{section.title}</h4>
                      <ul className="space-y-1">
                        {section.items.map((item, itemIndex) => (
                          <li key={itemIndex} className="text-xs text-black dark:text-gray-300 pl-3 relative">
                            <span className="absolute left-0 top-1 w-1 h-1 bg-quantum-blue-light rounded-full"></span>
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>

                <div className="mt-6 p-3 bg-indigo-50 dark:bg-transparent dark:bg-gradient-to-r dark:from-quantum-blue-dark/50 dark:to-quantum-purple-dark/50 rounded-lg border border-white/10">
                  <p className="text-xs text-black dark:text-gray-300">
                    <strong className="text-white">Example:</strong> For a language called &quot;MyFramework&quot;,
                    create <code className="text-quantum-blue-light">myframework_to_qasm.py</code> with
                    function <code className="text-quantum-blue-light">convert_myframework_to_qasm3()</code>
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
