import type { Metadata } from 'next'
import { Nav } from '@/components/nav'
import { ToastProvider } from '@/components/toast-provider'
import { ErrorBoundary } from '@/components/error-boundary'
import './globals.css'

export const metadata: Metadata = {
  title: 'GEO Insurance RAG Admin',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[hsl(var(--background))]">
        <ToastProvider>
          <Nav />
          <main className="p-6">
            <ErrorBoundary>{children}</ErrorBoundary>
          </main>
        </ToastProvider>
      </body>
    </html>
  )
}
