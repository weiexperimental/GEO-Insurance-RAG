'use client'
import React from 'react'

interface Props {
  children: React.ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary]', error, info)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[200px] flex-col items-center justify-center gap-4 rounded-md border border-zinc-700 bg-zinc-900 p-8 text-zinc-100">
          <div className="text-sm font-semibold">Something went wrong</div>
          {this.state.error && (
            <div className="max-w-lg rounded border border-zinc-700 bg-zinc-800 px-4 py-3 font-mono text-xs text-zinc-400">
              {this.state.error.message}
            </div>
          )}
          <button
            onClick={this.handleReset}
            className="rounded-md border border-zinc-600 bg-zinc-800 px-4 py-1.5 text-xs text-zinc-200 transition-colors hover:bg-zinc-700 hover:text-white"
          >
            Try Again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
