'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

const links = [
  { href: '/', label: 'Overview' },
  { href: '/documents', label: 'Documents' },
  { href: '/graph', label: 'Graph' },
  { href: '/playground', label: 'Playground' },
  { href: '/chunks', label: 'Chunks' },
  { href: '/eval', label: 'Eval' },
  { href: '/queries', label: 'Queries' },
  { href: '/logs', label: 'Logs' },
]

export function Nav() {
  const pathname = usePathname()

  return (
    <header className="flex items-center justify-between border-b border-[hsl(var(--border))] px-6 py-3">
      <span className="text-sm font-semibold">GEO Insurance RAG</span>
      <nav className="flex gap-1">
        {links.map(({ href, label }) => {
          const active = href === '/' ? pathname === '/' : pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={`rounded px-3 py-1.5 text-xs transition-colors ${
                active
                  ? 'bg-[hsl(var(--muted))] text-white'
                  : 'text-[hsl(var(--muted-foreground))] hover:text-white'
              }`}
            >
              {label}
            </Link>
          )
        })}
      </nav>
    </header>
  )
}
