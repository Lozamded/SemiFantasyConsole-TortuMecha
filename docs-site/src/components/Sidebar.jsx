import { Fragment } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { nav } from '../nav.js'

export default function Sidebar() {
  const { pathname } = useLocation()

  return (
    <aside className="sidebar">
      <div className="brand">TortoiseMecha</div>
      <div className="brand-sub">Semi-fantasy console docs</div>
      <nav>
        {nav.map((group) => (
          <Fragment key={group.title}>
            <div className="group-title">{group.title}</div>
            <ul>
              {group.items.map((item) => (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    className={pathname === item.path ? 'active' : undefined}
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </Fragment>
        ))}
      </nav>
    </aside>
  )
}
