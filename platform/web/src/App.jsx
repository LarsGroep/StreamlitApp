import React from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Search from './pages/Search'
import ArtistProfile from './pages/ArtistProfile'
import Discover from './pages/Discover'

const nav = [
  { to: '/',         label: 'Momentum' },
  { to: '/discover', label: 'Discover' },
  { to: '/search',   label: 'Search'   },
]

export default function App() {
  return (
    <div className="min-h-screen bg-lofi-bg text-lofi-text">
      <header className="border-b border-lofi-border px-6 py-4 flex items-center gap-8">
        <span className="text-lofi-accent font-bold tracking-widest uppercase text-sm">
          LOFI Intelligence
        </span>
        <nav className="flex gap-6">
          {nav.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) =>
                `text-sm transition-colors ${isActive ? 'text-lofi-accent' : 'text-lofi-muted hover:text-lofi-text'}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="px-6 py-8 max-w-7xl mx-auto">
        <Routes>
          <Route path="/"              element={<Dashboard />} />
          <Route path="/discover"      element={<Discover />} />
          <Route path="/search"        element={<Search />} />
          <Route path="/artists/:id"   element={<ArtistProfile />} />
        </Routes>
      </main>
    </div>
  )
}
