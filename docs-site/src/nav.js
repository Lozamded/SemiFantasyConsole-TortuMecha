// Single source of truth for the whole site's structure: sidebar groups,
// page order, and (via flatPages) the prev/next chain used by <PageNav/>.
// Add or reorder a page here and the sidebar + prev/next links everywhere
// update automatically — no more hand-editing 24 files per reorder.
export const nav = [
  {
    title: '1 · Get started',
    items: [
      { path: '/', label: 'Overview' },
      { path: '/get-started/install-sbc', label: 'Install on an SBC' },
      { path: '/get-started/cart-reader', label: 'Physical cart reader' },
    ],
  },
  {
    title: '2 · TortoiseStudio',
    items: [
      { path: '/studio/overview', label: '1. Overview & workflow' },
      { path: '/studio/palette', label: '2. Palette' },
      { path: '/studio/pixel-editors', label: '3. Sprite, tileset & background' },
      { path: '/studio/object-scene', label: '4. Object & scene editors' },
      { path: '/studio/gui-hud', label: '5. GUI/HUD editors' },
      { path: '/studio/fonts-audio', label: '6. Fonts & audio' },
      { path: '/studio/build-test', label: '7. Build & test' },
    ],
  },
  {
    title: '3 · Walkthrough',
    items: [
      { path: '/walkthrough/first-scene', label: '1. Build your first scene' },
      { path: '/walkthrough/tour', label: '2. Guided tour' },
    ],
  },
  {
    title: '4 · File Formats',
    items: [
      { path: '/formats/overview', label: '1. Project & palette' },
      { path: '/formats/scene', label: '2. Scenes' },
      { path: '/formats/object', label: '3. Objects' },
      { path: '/formats/sprite-tileset', label: '4. Sprites & tilesets' },
      { path: '/formats/background', label: '5. Backgrounds' },
      { path: '/formats/gui', label: '6. GUI layers & elements' },
      { path: '/formats/fonts', label: '7. Fonts' },
      { path: '/formats/dialogue', label: '8. Dialogues' },
    ],
  },
  {
    title: '5 · Scripting API',
    items: [
      { path: '/scripting/how-it-fits-together', label: '1. How it fits together' },
      { path: '/scripting/overview', label: '2. Overview & main.py' },
      { path: '/scripting/objects', label: '3. Object scripts' },
      { path: '/scripting/gui', label: '4. GUI layer scripts' },
      { path: '/scripting/subsystems', label: '5. Subsystems' },
      { path: '/scripting/reference', label: '6. Reference & imports' },
    ],
  },
]

// Flat, ordered list of every page across every group — the sequence
// <PageNav/> walks for "previous"/"next".
export const flatPages = nav.flatMap((group) => group.items)
