import { Link } from 'react-router-dom'
import PageNav from '../components/PageNav.jsx'

export default function Home() {
  return (
    <>

    <h1>TortoiseMecha Documentation</h1>
    <p className="subtitle">A semi-fantasy console built with PyGame, targeting low-spec ARM single-board computers.</p>
    <p>TortoiseMecha ships three packages: <code>tortoisengine</code> (headless engine and export pipeline),
    <code>tortoiseplayer</code> (the pygame runner for projects and <code>.tortucart</code> bundles), and
    <code>TortoiseStudio</code> (the PyQt6 visual editor).</p>

    <h2>Where to start</h2>
    <div className="card-grid">
      <Link className="card" to="/get-started/install-sbc" style={{ textDecoration: 'none' }}>
        <h3>Install on an SBC</h3>
        <p>Get a built cart running on ARM SBC like Raspberry Pi, Orange Pi, or Radxa board.</p>
      </Link>
      <Link className="card" to="/studio/overview" style={{ textDecoration: 'none' }}>
        <h3>TortoiseStudio</h3>
        <p>The visual editor: window layout, project workflow, every asset editor, and building executables.</p>
      </Link>
      <Link className="card" to="/walkthrough/first-scene" style={{ textDecoration: 'none' }}>
        <h3>Walkthrough</h3>
        <p>Real TortoiseStudio screenshots — build a small project from scratch, then a guided tour of a full game.</p>
      </Link>
      <Link className="card" to="/formats/overview" style={{ textDecoration: 'none' }}>
        <h3>File Formats</h3>
        <p>The project manifest and every asset format — scenes, objects, sprites, tilesets, backgrounds, GUI layers, fonts.</p>
      </Link>
      <Link className="card" to="/scripting/overview" style={{ textDecoration: 'none' }}>
        <h3>Scripting API</h3>
        <p>main.py hooks, object &amp; GUI layer scripts, instance_api, and every engine subsystem.</p>
      </Link>
    </div>

    <h2>Recommended reading order</h2>
    <p>The sidebar is numbered in the order we'd actually read it in:</p>
    <ol className="steps">
      <li>
        <h3>TortoiseStudio</h3>
        <p>Start with the editor's UI — it's how you'll touch every asset type from here on, so the rest of
        the docs assume you already know your way around its tabs and panels.</p>
      </li>
      <li>
        <h3>Walkthrough</h3>
        <p>Real screenshots of that same UI building something, and touring a finished project — a hands-on
        checkpoint before the reference material.</p>
      </li>
      <li>
        <h3>File Formats</h3>
        <p>Now that you've produced these files yourself in TortoiseStudio, it's worth knowing exactly what's
        in them — useful for hand-editing, version control diffs, and understanding what a script can rely on.</p>
      </li>
      <li>
        <h3>Scripting API</h3>
        <p>Last, because scripting is where everything meets: the files TortoiseStudio saved, the code it
        generated from them, and the logic you write by hand. That section opens with
        <Link to="/scripting/how-it-fits-together">How It Fits Together</Link>, which connects all three.</p>
      </li>
    </ol>
  
      <PageNav />
    </>
  )
}
