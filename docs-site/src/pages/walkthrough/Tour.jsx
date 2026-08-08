import { Link } from 'react-router-dom'
import PageNav from '../../components/PageNav.jsx'

export default function WalkthroughTour() {
  return (
    <>

    <h1>Walkthrough: Guided Tour</h1>
    <p className="subtitle">Every editor tab, shown with the real assets from the hello_tortu example project — "Mecha Turtle."</p>

    <p>The <Link to="/walkthrough/first-scene">previous page</Link> built something tiny from scratch. This
    page tours the same editors loaded with a real, finished project's content, so you can see what each one
    looks like once a project has real art, levels, and UI in it.</p>

    <h2>Game Preview</h2>
    <p>The title screen, rendered live by an embedded <code>TortoiseEngine</code> inside the editor — this is
    the actual game running, not a mockup:</p>
    <img className="shot" src="/assets/screenshots/tour-01-game-preview.png" alt="TortoiseStudio's Game Preview tab showing the hello_tortu example's title screen: a pixel-art mecha turtle robot illustration with the title 'Mecha Turtle', and Start game / Load game / Language menu options." />
    <p className="shot-caption">Game Preview — press F5 to also launch this as a real window, or F7 to debug-play with collider overlays. See <Link to="/studio/overview">Overview &amp; workflow</Link>.</p>

    <h2>Scene Editor</h2>
    <p>A real gameplay level: multiple tile layers, a parallax background, and a scene full of placed
    enemies, collision triggers, and dialogue-linked NPCs:</p>
    <img className="shot" src="/assets/screenshots/tour-02-scene-editor.png" alt="Scene Editor open on level_01, showing a tiled platformer level with clouds and sky, dialogue text overlays, a long list of placed objects (robots, red slimes, enemycolliders, dialogue icons) in the Objects in Scene panel, and the tile layer / camera side panel on the right." />
    <p className="shot-caption">level_01.tortuscene — a dozen-plus placed object instances, each with its own id and links (visible in the Objects in Scene list).</p>
    <p>Full reference: <Link to="/studio/object-scene">Object &amp; scene editors</Link>.</p>

    <h2>Tileset Editor</h2>
    <img className="shot" src="/assets/screenshots/tour-03-tileset-editor.png" alt="Tileset Editor open on terrain.tortutileset, showing an imported tile sheet on the left, an edited tile in the center, and a tile strip at the bottom with many terrain tiles." />
    <p className="shot-caption">terrain.tortutileset — a full imported tile sheet, sliced and stacked with per-tile collision.</p>

    <h2>Background Editor</h2>
    <img className="shot" src="/assets/screenshots/tour-04-background-editor.png" alt="Background Editor open on bg1.tortubackground, showing a parallax mountain-and-cloud background image wider than the screen, with a vertical camera-position guide line and palette swatches on the right." />
    <p className="shot-caption">bg1.tortubackground — 312×198px (1.2× screen width), painted with the same Pencil/Eraser/Eyedropper/Paint Bucket tools as sprites.</p>

    <h2>Object Editor</h2>
    <img className="shot" src="/assets/screenshots/tour-05-object-editor.png" alt="Object Editor open on mechaturtle.tortuobject, the player character, showing its idle sprite with an origin marker and collider box, and a long list of animations (idle, walk, jump, fall, attack, damage, air_attack, crouch, defeated) and two named colliders (body, head)." />
    <p className="shot-caption">mechaturtle.tortuobject — the player character prefab: 9 animations, two named colliders (body, head).</p>

    <h2>GUI Layer Editor</h2>
    <img className="shot" src="/assets/screenshots/tour-06-gui-layer-editor.png" alt="GUI Layer Editor open on hud.tortuguilayer, showing a lives counter icon, a 'x6' text label, a gears counter, and three life-pip placeholder circles, with Objects, Text Labels, and Tiled Rects panels on the right." />
    <p className="shot-caption">hud.tortuguilayer — the in-game HUD: text labels, repeat sprites (life pips), and placed icon objects. See <Link to="/studio/gui-hud">GUI/HUD editors</Link>.</p>

    <h2>Palette Editor</h2>
    <img className="shot" src="/assets/screenshots/tour-07-palette-editor.png" alt="Palette Editor showing the full 86-slot default palette grid with index 85 grayed out as reserved/transparent, and the Edit Selected Slot panel showing slot 0's hex value #1a1c2e." />
    <p className="shot-caption">The project's default palette — all 86 slots, index 85 reserved for transparency. See <Link to="/studio/palette">Palette</Link> for how a scene's palette actually relates to the tilesets, sprites, and backgrounds placed in it.</p>

    <h2>Font Editor</h2>
    <img className="shot" src="/assets/screenshots/tour-08-font-editor.png" alt="Font Editor's Text fonts tab open on VCR.tortufont, showing a console-screen preview mockup rendering '¡Hola!' and 'Score: 42 — ñáéíóú' in a monospace pixel font, with Size, Line height, and Latin-1 charset fields on the right." />
    <p className="shot-caption">VCR.tortufont — 223 baked glyphs from a Latin-1 charset, previewed against a cyan frame marking the real 264×198 game viewport.</p>

    <h2>Sound Editor</h2>
    <img className="shot" src="/assets/screenshots/tour-09-sound-editor.png" alt="Sound Editor showing three audio channels (music, game_sfx, ui_sfx) out of a 12-channel limit, and a Music Creator tab displaying a 'Coming soon' placeholder for a future step-sequencer." />
    <p className="shot-caption">Three configured channels — see <Link to="/scripting/subsystems">Subsystems</Link> for how scripts read channel volume at runtime.</p>

    <h2>Game Settings</h2>
    <img className="shot" src="/assets/screenshots/tour-10-game-settings.png" alt="Game Settings tab showing Game name 'Hello Tortoise', Cart name 'hello_tortu', Game FPS 60, Start scene 'scenes/title.tortuscene', empty Author/Description fields, and a Test Play Fullscreen checkbox." />
    <p className="shot-caption">The project's own tortu.project fields, editable as a form instead of hand-editing JSON. See <Link to="/formats/overview">Project &amp; palette</Link> for the underlying file.</p>

      <PageNav />
    </>
  )
}
