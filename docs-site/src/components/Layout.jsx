import { Outlet, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import Sidebar from './Sidebar.jsx'

export default function Layout() {
  const { pathname } = useLocation()

  // Static-site behavior: land at the top of the new page on navigation,
  // like a normal document load would.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <div className="layout">
      <Sidebar />
      <main>
        <Outlet />
      </main>
    </div>
  )
}
