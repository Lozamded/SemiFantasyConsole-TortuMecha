import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import { flatPages } from './nav.js'

// Every page component, eagerly bundled — keyed by its file path.
const modules = import.meta.glob('./pages/**/*.jsx', { eager: true })

function kebabToPascal(segment) {
  return segment.split('-').map((w) => w[0].toUpperCase() + w.slice(1)).join('')
}

// A page's route (from nav.js, the single source of truth) maps onto its
// component file by convention: /studio/pixel-editors -> pages/studio/PixelEditors.jsx.
// Add a page by adding one line to nav.js and creating the matching file —
// no route table to keep in sync by hand.
function moduleKeyFor(route) {
  if (route === '/') return './pages/Home.jsx'
  const segments = route.split('/').filter(Boolean)
  const file = kebabToPascal(segments[segments.length - 1]) + '.jsx'
  const folder = segments.slice(0, -1).join('/')
  return folder ? `./pages/${folder}/${file}` : `./pages/${file}`
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          {flatPages.map(({ path }) => {
            const key = moduleKeyFor(path)
            const mod = modules[key]
            if (!mod) {
              throw new Error(`nav.js references "${path}" but ${key} does not exist`)
            }
            return <Route key={path} path={path} element={<mod.default />} />
          })}
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
