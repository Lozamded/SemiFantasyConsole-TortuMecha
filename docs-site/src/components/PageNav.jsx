import { Link, useLocation } from 'react-router-dom'
import { flatPages } from '../nav.js'

// Prev/next links, fully computed from nav.js — no page ever hardcodes its
// neighbors, so reordering the site is a one-line change in nav.js instead
// of hunting down every affected page's page-nav block.
export default function PageNav() {
  const { pathname } = useLocation()
  const index = flatPages.findIndex((p) => p.path === pathname)
  if (index === -1) return null

  const prev = index > 0 ? flatPages[index - 1] : null
  const next = index < flatPages.length - 1 ? flatPages[index + 1] : null

  return (
    <div className="page-nav">
      {prev ? <Link to={prev.path}>&larr; {prev.label.replace(/^\d+\.\s*/, '')}</Link> : <span></span>}
      {next ? <Link to={next.path}>Next: {next.label.replace(/^\d+\.\s*/, '')} &rarr;</Link> : <span></span>}
    </div>
  )
}
