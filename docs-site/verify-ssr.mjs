// Server-side-renders every page listed in src/nav.js (the single source of
// truth for the site's routes) and checks for render errors, dead internal
// links, and missing screenshot files. Run after any content/nav change:
//   npm run verify
import fs from 'node:fs'
import { createServer } from 'vite'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { flatPages } from './src/nav.js'

function kebabToPascal(segment) {
  return segment.split('-').map((w) => w[0].toUpperCase() + w.slice(1)).join('')
}

function modulePathFor(route) {
  if (route === '/') return 'pages/Home.jsx'
  const segments = route.split('/').filter(Boolean)
  const file = kebabToPascal(segments[segments.length - 1]) + '.jsx'
  const folder = segments.slice(0, -1).join('/')
  return folder ? `pages/${folder}/${file}` : `pages/${file}`
}

const server = await createServer({ server: { middlewareMode: true }, appType: 'custom' })

const knownRoutes = new Set(flatPages.map((p) => p.path))
let ok = 0
const failed = []
const linkRe = /href="([^"]+)"/g
const imgSrcRe = /src="([^"]+)"/g

for (const { path: route } of flatPages) {
  const modPath = modulePathFor(route)
  try {
    if (!fs.existsSync(new URL(`./src/${modPath}`, import.meta.url))) {
      failed.push(`${route}: expected component file src/${modPath} does not exist`)
      continue
    }
    const mod = await server.ssrLoadModule(`/src/${modPath}`)
    const PageComp = mod.default
    const html = renderToStaticMarkup(
      React.createElement(MemoryRouter, { initialEntries: [route] }, React.createElement(PageComp))
    )

    const issues = []
    if (/undefined|\[object Object\]|NaN/.test(html)) issues.push('contains undefined/[object Object]/NaN')
    if (!html.includes('<h1')) issues.push('no <h1> found')

    for (const m of html.matchAll(linkRe)) {
      const href = m[1]
      if (href.startsWith('/') && !href.startsWith('/assets/') && !knownRoutes.has(href)) {
        issues.push(`dead link target: ${href}`)
      }
    }
    for (const m of html.matchAll(imgSrcRe)) {
      const src = m[1]
      if (src.startsWith('/assets/screenshots/') && !fs.existsSync(new URL(`./public${src}`, import.meta.url))) {
        issues.push(`missing image: ${src}`)
      }
    }

    if (issues.length) failed.push(`${route}: ${issues.join('; ')}`)
    else ok++
  } catch (err) {
    failed.push(`${route}: THREW ${err.message}`)
  }
}

await server.close()

console.log(`OK: ${ok}/${flatPages.length}`)
if (failed.length) {
  console.log('ISSUES:')
  for (const f of failed) console.log(' -', f)
  process.exit(1)
}
console.log('All pages in nav.js rendered cleanly — no dead links, no missing images, no missing component files.')
