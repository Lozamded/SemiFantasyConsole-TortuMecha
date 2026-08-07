import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function WalkthroughFirstScene() {
  return (
    <>

    <h1>Walkthrough: Build Your First Scene</h1>
    <p className="subtitle">Every screenshot below is the real TortoiseStudio UI, captured from an actual run — a new project, a hand-drawn sprite, a tileset, an object, and a scene, built from nothing.</p>

    <div className="callout">
      <strong>Follow along</strong>
      This walkthrough builds a tiny project called "Turtle Trail": one sprite, one tileset, one object, one
      scene. It exercises the same New Project → New Sprite → New Object → New Scene flow you'd use for a
      real game — just with deliberately small assets so each step is easy to see in full.
    </div>

    <h2>1. Create the project</h2>
    <p>File → New Project… only asks where to put it — no setup wizard. It scaffolds the folder structure,
    writes a starter <code>main.py</code> (a bouncing rectangle and the TortoiseStudio wordmark), and opens
    straight into the Game Preview tab:</p>
    <img className="shot" src="/assets/screenshots/demo-01-empty-project.png" alt="TortoiseStudio main window right after creating a new project, showing the default bouncing-rectangle main.py running in the Game Preview tab, with the empty project tree on the left." />
    <p className="shot-caption">Game Preview tab immediately after File → New Project…, running the default main.py stub.</p>
    <p>See <Link to="/studio/overview">Overview &amp; workflow</Link> for what every part of this window does.</p>

    <h2>2. Draw a sprite</h2>
    <p>Sprite Editor → New Sprite… asks for a name, size in 4px blocks, and a palette:</p>
    <img className="shot" src="/assets/screenshots/dialog-new-sprite.png" alt="The New Sprite dialog: Name field set to hero, Blocks wide and Blocks tall spinboxes both at 4, a Pixel size readout of 16x16px (4x4 blocks), and a Palette dropdown set to default." />
    <p className="shot-caption">New Sprite… — sizes are authored in 4px blocks, not raw pixels.</p>
    <p>A fresh sprite starts fully transparent. Painting with Pencil/Eraser/Eyedropper (right-click cycles
    between them) against the palette swatch grid produces something like this — a small round "shell" icon:</p>
    <img className="shot" src="/assets/screenshots/demo-02-sprite-editor.png" alt="Sprite Editor showing a small hand-painted green shell/turtle icon on a 16x16 pixel canvas, with the block grid overlay visible, palette swatches on the right, and Pencil tool active." />
    <p className="shot-caption">The finished 16×16 sprite — block grid on, palette swatches on the right pick the pencil color.</p>
    <p>Full editor reference: <Link to="/studio/pixel-editors">Sprite, tileset &amp; background</Link>.</p>

    <h2>3. Build a tileset</h2>
    <p>Same idea for ground tiles — paint a tile, set its collision, commit it to the stack, repeat:</p>
    <img className="shot" src="/assets/screenshots/demo-03-tileset-editor.png" alt="Tileset Editor with two 8px tiles in the stack — a grass-topped tile and a plain dirt tile — the Collision field set to solid, One way set to none, and the edit buffer showing the grass tile's pixel art." />
    <p className="shot-caption">Two tiles committed to the stack — collision is set per-tile via the Collision tab, independent of the pixel art.</p>
    <p>Note the <strong>Collision: solid</strong> field on the right — this is what makes the ground actually
    stop the player at runtime, entirely separate from how the tile looks. See
    <Link to="/formats/sprite-tileset">Sprites &amp; tilesets</Link> for the full collision-type/one-way model.</p>

    <h2>4. Make an object from the sprite</h2>
    <p>Object Editor → New Object… picks a name, a first animation name, and which sprite to use:</p>
    <img className="shot" src="/assets/screenshots/dialog-new-object.png" alt="The New Object dialog: Name field set to object, First animation name set to idle, and a Sprite dropdown." />
    <p className="shot-caption">New Object… — every object needs at least one animation right away.</p>
    <p>The origin (yellow crosshair) and collider box are dragged directly on the preview canvas, not just
    typed as numbers:</p>
    <img className="shot" src="/assets/screenshots/demo-04-object-editor.png" alt="Object Editor showing the turtle shell sprite with a yellow origin crosshair and a yellow collider box drawn around most of the sprite, plus the full form of animation, collider, origin, and custom variable fields on the right." />
    <p className="shot-caption">Origin crosshair and collider box, both draggable on the canvas — X/Y/Width/Height on the right stay in sync.</p>
    <p>Full field reference: <Link to="/studio/object-scene">Object &amp; scene editors</Link>.</p>

    <h2>5. Place it in a scene</h2>
    <p>New Scene… just needs a name and palette:</p>
    <img className="shot" src="/assets/screenshots/dialog-new-scene.png" alt="The New Scene dialog: Name field set to level_01 and a Palette dropdown set to default." />
    <p className="shot-caption">New Scene… — everything else (tile layers, backgrounds, objects) is added from inside the editor.</p>
    <p>From here: assign the tileset to the ground tile layer, paint a strip of ground tiles across the
    bottom, add a sky-blue background layer, and drop the object onto the map (dragged straight from the
    project tree, or placed via the Objects tab below the canvas):</p>
    <img className="shot" src="/assets/screenshots/demo-05-scene-editor.png" alt="Scene Editor showing a full 264x198 scene: a flat blue sky background, a strip of ground tiles across the bottom two rows, and a small green turtle object standing on the ground. The right panel shows Scripts, Backgrounds, GUI Layers, Tile layers, Camera, and Map sections; the Objects in Scene panel lists the placed turtle instance." />
    <p className="shot-caption">A complete (tiny) scene: background, tile ground, and one placed object — visible both on the map and in the Objects in Scene list on the right.</p>
    <p>Full side-panel reference: <Link to="/studio/object-scene">Object &amp; scene editors</Link>.</p>

    <h2>6. Ready to build</h2>
    <p>Once a project has a start scene set (Game Settings tab), <strong>Build → Export .tortucart…</strong>
    packages it, and <strong>Build → Build Executable…</strong> opens this dialog to produce a standalone
    binary — here, on a host that already has Podman, <code>passt</code>, and QEMU installed, so both ARM
    targets are available:</p>
    <img className="shot" src="/assets/screenshots/dialog-build-executable.png" alt="The Build Executable dialog: a Cart path label, a Target architectures group with Current platform (x86_64) checked, and ARM64 / ARMhf checkboxes enabled and unchecked, a large empty build log area, and Build/Close buttons." />
    <p className="shot-caption">Build Executable… — ARM64/ARMhf are enabled here because this host already has the cross-compile toolchain set up (see Install on an SBC).</p>
    <p>Full build reference: <Link to="/studio/build-test">Build &amp; test</Link>, and what to do with the
    result: <Link to="/get-started/install-sbc">Install on an SBC</Link>.</p>

      <PageNav />
    </>
  )
}
