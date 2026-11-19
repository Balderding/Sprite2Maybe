# Research: 2D art into 3D, and making 2D art, with AI and without (2026-11-17)

What exists for (A) turning a flat sprite into a 3D object and (B) producing the 2D sprites themselves, by AI and by
plain algorithms or handwork, and what each means for this project (16 x 16 and 32 x 32 Ultima Underworld item
sprites, a first-person weapon, items lying in the world).

How to read it: most web sources on the AI tools are vendor pages and comparison blogs, so rankings, speeds and
memory figures are soft and sometimes contradict each other; where they do, both are given. Nothing here was tried on
our own sprites except what `sprite3d.py` does. "Not found" means the searches did not find it, not that it does not
exist.

## A. A flat sprite into a 3D object

### A1. Without AI

| Method | How it works | Tools that do it | Fit for us |
| --- | --- | --- | --- |
| **Extrusion (slab)** | Every opaque pixel becomes a block of the same thickness; side faces where a pixel meets nothing. | Minecraft's item models (made in code from the 16 x 16 picture), Voxel Forge, Pixel to 3D Batch Builder, Grab3D "Voxel" style, `sprite3d.py --method slab` | Works on anything at once. Edge-on it is a plate. |
| **Inflation (pillow)** | Thickness grows with a pixel's distance from the outline, or from solving a smoothing equation over the shape. | Grab3D "Inflate" and "Rounded", GazPrash 2d-to-3d-voxelizer (silhouette thickness), `inflation_py`, Laigter's bevel (for normal maps), `sprite3d.py --method round` | Good for blobs (potions, food, gems). A blade comes out as a pillow. |
| **By part (profiles)** | The sprite is split into parts; each gets its own cross-section (blade ridge, round shaft, bevelled plate). | `sprite3d.py --method shaped`. Morrowshore's Voxelizer is the nearest outside tool: the thickness is painted by hand onto the sprite. | Best shape for weapons; needs a parts picture per sprite (guessed, then corrected). |
| **Several views carved together (visual hull)** | A front, a side and a top picture are each extruded through the block and intersected. | Pixhull (open source, browser), GazPrash's Dual and Quad modes | Would give true thickness, but needs a side and a top drawing of every item. Worth it only for a few hero items. |
| **Sprite stacking** | The object is drawn as horizontal slices, one picture a layer; the layers are drawn one pixel apart and all turned by the same angle. | SpriteStack.io, the SpriteStacked plugin for Aseprite, Chequered Ink's SpriteStack previewer | A look for top-down 2D games; in a real 3D renderer it is just a voxel model made the hard way. Not for us. |
| **Depth map per sprite, no model** | Each body-part sprite carries a depth map (made automatically, editable); a shader regenerates the sprite as the part turns. | Smack Studio (patented, 2023; built on Unreal) | Proves that "a sprite plus per-pixel depth" is enough for convincing turns. Our height field is the same idea, turned into a mesh. |
| **Sketch inflation with parts** | Outlines drawn as overlapping regions are inflated and stitched (a leg joined to a body) in one solve. | Monster Mash (Google and others, SIGGRAPH Asia 2020, open source, exports .glb) | Made for soft creatures, not hard-edged weapons. Could suit creature sprites one day. |
| **Hand-made voxels** | One voxel per pixel, built by a person, unseen sides invented. | MagicaVoxel; Voxel Doom did every Doom sprite this way | The best look, all handwork, per item. |
| **Hand-made low-poly with pixel textures** | A person models a few dozen faces and paints them in pixels. | Blockbench (free, generates the UV layout, paint on the model), picoCAD 2, Crocotile 3D | The standard way retro shooters make weapon models. A fallback for the few items the generator does badly. |

Numbers worth keeping: a 32 x 32 sword is about 1,400 triangles extruded with merged faces and about 5,300 as
separate cubes (Grab3D); ours are 700 to 850 faces unmerged because only the outside is built.

### A2. With AI (one picture in, a textured mesh out)

The open models people run on their own PC, as of late 2026:

| Model | Who | What comes out | Memory to run | Speed | Licence |
| --- | --- | --- | --- | --- | --- |
| **TRELLIS.2 (4B)** | Microsoft | Mesh with full materials (PBR), good on thin and open shapes | 24 GB stated; community reports from 8 to 16 GB at lower detail | 1 to 2 minutes on an RTX 4090 in most reports | MIT (one source says Apache 2.0) |
| **Hunyuan3D 2.1** | Tencent | Mesh with full materials; strongest textures | about 10 GB shape only, 29 GB with textures | minutes | Tencent's own; regions excluded (EU, UK, South Korea) |
| **Stable Fast 3D** | Stability AI | Mesh, unlit colour plus material values | about 6 GB | about half a second | Stability community licence |
| **TripoSR** | Tripo + Stability | Mesh with vertex colours, rough | about 4 GB | about half a second | MIT |

Hosted services add Meshy (has a "Voxel" style), Tripo, Rodin (Hyper3D, has a pixel-art style page: a normal mesh
dressed with low-resolution textures) and Hunyuan3D v3.

What matters for sprites:

- **They want big, clean pictures.** The guides give 512 x 512 as the floor and 1024 x 1024 as the target, and list
  low-resolution input as a problem. Our sprites are 16 x 16. They would have to be enlarged about 32 times first,
  and how the enlarging is done (plain blocks, an edge-aware scaler such as xBR, or an AI upscaler) changes what the
  model thinks it is looking at. No source tested this.
- **They do not keep pixels.** The output is a smooth mesh with a smooth texture (Hunyuan3D's texture step runs at
  512 and then through an AI upscaler). A pixel-art look has to be put back afterwards, by re-texturing or by
  rendering small. Colours will not be the sprite's own.
- **They invent the back and the thickness**, which is the one thing our generator cannot know. For a sword that is
  trivial; for a skull, a pouch or a creature it is the whole value.
- **No first-hand reports were found** of anyone feeding small game sprites to these models, good or bad.

AI that outputs voxels: text2vox (open source: a picture from Flux, a mesh from Hunyuan3D-2, then a mesh-to-voxel
converter, up to 96 cubed), and the hosted VoxAI, VoxelAI Studio and Sorceress, which export MagicaVoxel `.vox`.
All of them are "make a mesh, then chop it into cubes", so the pixels of the source sprite are still not kept.

Related AI building blocks:

- **Depth from one picture** (Depth Anything V2 and 3, Depth Pro, Marigold): a grey depth picture that can displace
  a flat grid into a relief. They are trained on photographs; nothing found on pixel art. A relief is one-sided, and
  for a weapon our part profiles already give a cleaner relief.
- **New views from one picture** (Zero123, Zero123++, SV3D, MV-Adapter, 2026's turntable-video models): the model
  draws the object from other angles. Useful as reference for a hand-drawn side view; not pixel-exact.

### A3. What this says for the project

1. **Weapons and other hard, flat things: keep the generator** (`sprite3d.py`, shaped). It is exact in colour,
   instant, repeatable, and needs no download. AI adds nothing a sword needs.
2. **Round, lumpy or asymmetric items** (skulls, pouches, food, bones, gems): the "round" method is the first try;
   an AI model is the only route that invents a believable back. A fair experiment: one sprite enlarged three ways
   into TRELLIS.2 on the 4090, then the result re-coloured from the sprite's own palette. Cost: a 10 to 12 GB
   download and 40 GB of disk for ComfyUI's node, about two minutes a model. Not started; needs the user's word
   (models were removed from ComfyUI on 2026-11-16 at their request).
3. **A side view for hero items** (the visual-hull route) is the non-AI way to get true thickness where it matters.
4. **Hand-made in Blockbench** is the fallback for anything both routes do badly.

## B. Making the 2D sprites themselves

### B1. Without AI

| Method | What it is | Tools |
| --- | --- | --- |
| **Turn and redraw** | Rotate a sprite and re-sample it cleanly. | cleanEdge (what our upright sprites use), RotSprite (Aseprite's), xBR / hqx for enlarging |
| **Mirrored-mask generators** | A small mask says which cells are always empty, always filled, or random; one half is rolled and mirrored. The classic "pixel spaceships" method (Dave Bollinger). | pixel-sprite-generator (JavaScript, with Dart, Haxe and Python ports), CryPixels |
| **Part assembly** | Icons built from libraries of blades, hilts, gems and so on, combined and re-coloured. | Icon Machine (item icons), Tiny Gun Generator |
| **Render a 3D model small** | Model and animate in 3D, render tiny with toon shading and no smoothing, keep a normal map per frame for lighting. Dead Cells was made this way (characters about 50 pixels tall); flickering pixels were its unsolved problem. | Blender (filter width near zero, toon shader), BlendNote's 25 pixel shaders, pseudo-pixel (a 2D reference to model, rig, small render, sprite sheet, driven by a coding agent) |
| **Sprite stacking** | See A1. | SpriteStack |

The 3D-to-sprite route is the reverse of our tool and closes a loop: once an item has a 3D model, every view of it
(inventory icon, lying on the floor from any side, held in the hand) can be rendered from the one model in the
sprite's own colours. `sprite3d.py`'s `--view` already does a plain version of this.

### B2. With AI

| Tool | Strength | Notes |
| --- | --- | --- |
| **PixelLab** | From one facing it draws the other 3 or 7; skeleton animation; edits that keep the character; tilesets | 16 to 512 px; about 12 USD a month; has an API and an MCP server, so it can be scripted |
| **Retro Diffusion** | Output locked to the pixel grid, no blur or smoothing | 16 to 384 px; about 0.03 USD an image; an Aseprite extension (65 USD once). Sources disagree on whether it does directional rotation; a recent one says it now does |
| **Others** | SpriteLab, Sprixen, Sprite AI (8 facings from one sprite); Ludo renders up to 8 facings from a 3D model | Vendor claims; no independent test of how consistent the facings are was found |

A workflow one comparison recommends: make the key sprite in Retro Diffusion, turn and animate it in PixelLab.

For us these matter less than they look: the game's art already exists and the rule is to keep its colours. Where
they could help is *new* art in the old style (an item the original never drew), which `tools\art_to_sprite.py`
already brings down to 64 x 64 in a sprite's own colours.

## Sources

Image to 3D (AI): [3D AI Studio, best image to 3D tools 2026](https://www.3daistudio.com/3d-generator-ai-comparison-alternatives-guide/best-image-to-3d-tools-2026),
[Fuser, best AI 3D model generators](https://fuser.studio/articles/best-ai-3d-model-generators),
[Pixazo, open-source 3D generation](https://www.pixazo.ai/blog/best-open-source-3d-model-generation-apis),
[Triposplat, 12 tools compared](https://triposplat.com/blog/best-3d-ai-generators-2026),
[the3dai, 7 tools compared](https://the3dai.com/best-image-to-3d-ai),
[BuilderAI, single image to 3D guide](https://builderai.tools/blog/single-image-to-3d-model-pipeline-2026),
[trellis2.app, best image-to-3D models on Hugging Face](https://trellis2.app/blog/best-image-to-3d-models-huggingface),
[Trify3D, best AI 3D model generators](https://trify3d.com/blog/best-ai-3d-model-generators),
[fal, Hunyuan 3D v3 guide](https://fal.ai/learn/devs/hunyuan-3d-v3-prompt-guide),
[fal, TRELLIS 2 guide](https://fal.ai/learn/devs/trellis-2-image-to-3d-prompt-guide),
[lilting.ch, input specs and best practices](https://lilting.ch/en/articles/ai-3d-generation-tools-comparison),
[Hunyuan3D 2.0 paper](https://arxiv.org/html/2501.12202v1),
[TRELLIS.2-4B model card](https://huggingface.co/microsoft/TRELLIS.2-4B/blob/main/README.md),
[Hunyuan3D-2.1 demo script](https://www.huggingface.co/tencent/Hunyuan3D-2.1/blob/main/demo.py),
[Hyper3D pixel-art style](https://hyper3d.ai/styles/pixel-art),
[Meshy, pixel-art game with three.js](https://www.meshy.ai/tutorials/make-a-pixel-art-game-with-threejs)

Running TRELLIS.2 locally: [The Local Lab installer](https://www.patreon.com/TheLocalLab/posts/trellis-2-sota-146806567),
[Trify3D, Trellis 2 in ComfyUI](https://trify3d.com/blog/trellis-2-comfyui),
[trellis2.app, ComfyUI workflow](https://trellis2.app/blog/trellis-2-comfyui-workflow),
[trellis2.app, install guide](https://trellis2.app/blog/how-to-install-trellis-2),
[Earngenix, TRELLIS 2 in ComfyUI](https://www.earngenix.com/workflows/trellis2-image-to-3d-comfyui)

AI voxels: [text2vox](https://github.com/gfodor/text2vox), [VoxAI](https://www.voxelai.ai/),
[VoxelAI Studio](https://voxelai.studio/blog/best-voxel-software-tools),
[Sorceress voxel generator](https://sorceress.games/blog/ai-voxel-generator-rigged-characters-in-the-browser)

Depth and new views: [Depth Anything V2](https://fuser.studio/models/depth-anything-v2),
[Roboflow, depth estimation models](https://blog.roboflow.com/depth-estimation-models/),
[depth maps refined into meshes](https://arxiv.org/html/2410.03861v1),
[MonoRelief V2](https://arxiv.org/pdf/2508.19555),
[sharp occlusion boundaries](https://arxiv.org/pdf/2002.12730),
[relief textures patent](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6424351),
[MV-Adapter](https://arxiv.org/pdf/2412.03632), [SV3D](https://arxiv.org/pdf/2403.12008),
[TAPESTRY](https://arxiv.org/pdf/2603.17735), [Animate3D](https://proceedings.neurips.cc/paper_files/paper/2024/file/e3b53f89136b1bc69a5714ea465f01b6-Paper-Conference.pdf)

Sprite to 3D without AI: [Pixel to 3D Batch Builder](https://reactorcore.itch.io/pixel-to-3d-batch-builder),
[2d-to-3d-voxelizer](https://github.com/GazPrash/2d-to-3d-voxelizer),
[Voxel Forge](https://litenight.itch.io/voxel-forge), [Pixhull](https://metalismaticus.github.io/Pixhull/),
[Morrowshore Voxelizer](https://morrowshore.com/tool/voxelizer/), [Grab3D Draw to 3D](https://grab3d.com/tools/draw-to-3d/),
[Smack Studio press page](https://smackstudio.com/press/),
[Smack Studio, 3D rotations for pixel art](https://smackstudio.com/a-brand-new-way-to-create-3d-rotations-for-pixel-art/),
[Smack Studio on Steam](https://store.steampowered.com/app/1739300/Smack_Studio/),
[Monster Mash source](https://github.com/google/monster-mash),
[Monster Mash paper](https://www.researchgate.net/publication/347591875_Monster_mash_a_single-view_approach_to_casual_3D_modeling_and_animation),
[Monster Mash overview](http://www.databloom.com/2021/04/09/monster-mash-a-sketch-based-tool-for-casual-3d-modeling-and-animation/)

Sprite stacking: [GameFromScratch on SpriteStack](https://gamefromscratch.com/spritestack-3d-pixel-art-tool/),
[Rail Mania devlog](https://darkshadow4242.itch.io/rail-mania/devlog/1787382/sprite-stacking-to-fake-3d-with-pixel-art),
[SpriteCook guide](https://www.spritecook.ai/blog/sprite-stacking-pixel-art),
[Flaming Stacks](https://blog.codemagic.io/flaming-stacks/),
[The Pixelnaut tutorial](https://thepixelnaut.com/articles/sprite-stacking-tutorial-create-3d-magic-from-2d-pixel-art/),
[Flowlab guide](https://community.flowlab.io/t/sprite-sandwich-a-guide-to-spritestacking/40779),
[SpriteStack on Hacker News](https://news.ycombinator.com/item?id=19325331)

Hand-made low-poly: [Blockbench and picoCAD](https://medium.com/@rikmgomes/blockbench-e-picocad-ferramentas-de-modelagem-3d-low-poly-c7b1ce911b6a),
[80.lv on Blockbench](https://80.lv/articles/create-texture-animate-low-poly-3d-models-with-this-tool),
[picoCAD 2](https://johanpeitz.itch.io/picocad2),
[Style3D, tools for retro 2.5D scenes](https://www.style3d.com/blog/which-tools-are-best-for-retro-2-5d-game-scenes/)

3D into pixel art: [Dead Cells deep dive](https://www.gamedeveloper.com/production/art-design-deep-dive-using-a-3d-pipeline-for-2d-animation-in-i-dead-cells-i-),
[Blender Artists, mimicking Dead Cells](https://blenderartists.org/t/mimicking-dead-cells-workflow-from-3d-animation-to-2d-pixel-animation/1124638),
[Blender Artists, Demon Overdrive](https://blenderartists.org/t/so-i-did-a-pixel-art-game-with-blender-and-unity/1169165),
[pseudo-pixel](https://github.com/craigrusselltiu/pseudo-pixel), [BlendNote](https://ashcruz.itch.io/blendnote),
[Devpost recreation](https://devpost.com/software/the-dead-cells-animation-pipeline)

Making sprites without AI: [pixel-sprite-generator](https://github.com/Mocker/pixel-sprite-generator),
[Python Sprite-Generator](https://github.com/MaartenGr/Sprite-Generator), [CryPixels](https://crypixels.com/),
[Random Sprite Generator](https://theonixie.itch.io/random-sprite-generator),
[itch.io procedural pixel-art tools](https://itch.io/tools/top-rated/tag-pixel-art/tag-procedural),
[scaling algorithms gallery](https://en.wikipedia.org/wiki/Comparison_gallery_of_image_scaling_algorithms)

Making sprites with AI: [Ludo, AI pixel art generators](https://ludo.ai/compare/best-ai-pixel-art-generators),
[Ludo, AI sprite generators](https://ludo.ai/compare/best-ai-sprite-generators),
[Retro Diffusion vs PixelLab](https://gamedevaihub.com/retro-diffusion-vs-pixellab/),
[Sprite AI, generators tested](https://www.sprite-ai.art/blog/best-pixel-art-generators-2026),
[SpriteGen roundup](https://spritegen.ai/blog/best-ai-sprite-generator-tools/)

## C. What we tried ourselves (2026-11-17, late)

Run on this PC through ComfyUI 0.35.1's own nodes (hidden, port 8190), scripts and results in `work\ai3d\`.
Models downloaded into `O:\Comfy-Desktop\ComfyUI-Shared\models`: Hunyuan3D 2.1 (7.4 GB) and the Pixal3D / TRELLIS.2
set (seven files, 14.5 GB).

1. **The raw sprite, enlarged, gives a flat card.** Hunyuan3D 2.1 made the axe and the potion about 1 pixel thick,
   the skull 1.8, the sack 2.5. Smoothing the stair-steps first changed nothing. Pixal3D did the same or worse (a
   nonsense box for the potion). The models read pixel art as a flat picture.
2. **Making the sprite look like a lit object first fixes it** (`prep_render.py`, no AI): drop the black outline,
   smooth the colours, add light and shade from a depth guessed by our own tool. The same models then give real
   volume: potion 7.4 pixels thick, skull 4.5, sack 5.8. Both models work with it; about 35 s a model on the 4090.
   This is our version of the "repaint it larger first" step the published Ultima Underworld model set describes.
3. **For weapons the AI is worse than our own tool:** the axe came out fat and lumpy. Keep "shaped" for them.
4. **The AI's shape poured back into our mesher** (`hybrid.py`): the AI mesh is lined up with the sprite, each sprite
   pixel takes its thickness from it, and `sprite3d.build_mesh` builds the model. Result: closed, 200 to 1,000 faces
   (the AI's own meshes have 200,000 to 5 million), every face one sprite pixel's own colour, the front exactly the
   sprite. 19 lumpy items done this way: `work\ai3d\show-batch-hybrid-1.png`, models in `work\ai3d\hybrid\`.
5. **The dark bands on the sides are gone:** `--outline flat` (now the default) keeps a dark outline as a thin flat
   rim round the model instead of letting it climb the sides.
6. A public precedent exists: github.com/abedegno/underworld-models (CC BY-SA 4.0), models for all the game's object
   kinds, made by repainting each sprite larger, then the Meshy service, then recolouring; thin items built as plain
   voxels from the sprite. Not looked at closely yet.

Not tried: Pixal3D's multi-view input with a mirrored back; depth estimation (MoGe) straight to a relief; the texture
stages of either model (we take colours from the sprite instead).

7. **Pixal3D with two views, the sprite as the front and its mirror as the back** (`more_trials.py mv`, 2026-11-18):
   it does not rescue a raw blocky sprite (the potion became a plate with a cross-piece, the axe stayed 2 pixels
   thick, the skull went from 1.0 to 2.9). With the lit pre-rendered picture it works and gave the roundest skull
   (6.2 pixels thick), but the potion was no better than with one view. About 30 to 50 s a model.
8. **Depth straight from a depth estimator** (MoGe-2, `more_trials.py moge`, 1 to 5 s a picture): on the raw sprite
   the depth is a flat plateau, the same "flat card" reading. On the lit pre-rendered picture it gives a sensible
   relief, but that relief is mostly our own guessed depth read back out of the shading we painted, so it adds
   little over using our depth directly.

So in every trial the deciding step was the same: the picture has to look like a lit solid object before any model
sees it. Which model then makes the shape matters much less.

## D. Controlling thickness by drawing, and the maths behind it (2026-11-18)

The question: the handle came out too thick, so how do we let a person draw on the 2D picture to make parts thinner
or thicker, and what does the literature say about turning a flat outline into a solid? About twenty-five years of
papers answer it, nearly all from "sketch-based modelling" and "single-view reconstruction". The main ideas, with what
each means for this tool:

### D1. Inflation: a height for every pixel of a flat shape

| Idea | The maths | What it means here |
| --- | --- | --- |
| **Teddy** (Igarashi, Matsuoka, Tanaka, SIGGRAPH 1999) | The outline's *chordal axis* (a skeleton) is found; each point is lifted as high as it is far from the outline, so wide parts are fat and narrow parts thin. | Where all of this started. Our "round" method is this idea on a pixel grid. |
| **Notes on inflating curves** (Baran, Lehtinen, MIT 2009) | Solve the Poisson equation ∇²h = −4 inside the outline with h = 0 on it, then take the height z = √h. On a disc h = 1 − x² − y², so z is exactly a half-sphere. The square root makes the slope infinite at the outline, so front and back meet edge-on with no crease. | The cleanest rule for a smooth round object: a sharp silhouette with no rim. The right-hand side (−4) is where thickness can be painted: a larger value in a region makes it puff more, a smaller one less. |
| **Puffball** (Twarog, Tappen, Adelson, 2012) | "Anywhere you can fit a ball is inside the shape": the solid is the union of every ball that fits inside the outline. A pixel's height is the largest √(r² − d²) over the inscribed balls (r a ball's radius, d the distance to its centre). | Our shaft rule (each row a circle as wide as the row) is this in one direction only. Puffball does it in every direction, so a handle drawn at a slant is still round, with no need to stand the sprite upright. |
| **Medial axis transform** (Blum 1967) and generalized cylinders (Gingold, Igarashi, Zorin 2009; 3-Sweep, Chen et al. 2013; rotational blending, Cherlin et al. 2005) | A shape is a skeleton line plus a radius at each point on it. A part is a "generalized cylinder": a circle (or any profile) swept along the skeleton, its radius set by the outline. | The right model for handles, shafts and blades. The radius should come from the **coloured width**, not the outline's (the fix made today); a painted radius scale makes it thinner or thicker along its length. |
| **Shape priors** (Oswald, Töppe, Cremers, TU Munich) | A height profile with an exponent k: k < 1 is round, k > 1 flatter on top, and as k → ∞ a box with walls at the outline. | One number that runs from "pillow" to "plate". A future Profile row (Round / Bevel / Flat) could be this exponent. |
| **Thin-plate / biharmonic surfaces** (Prasad et al. 2005; Repoussé, Joshi and Carr 2008; FiberMesh, Nealen et al. 2007) | Minimise bending energy (∇⁴h = 0, the biharmonic equation) under constraints; Repoussé controls the puff with the *mean curvature* stored on the outline, all in one linear solve. | Smoother than Poisson, with control over "this edge sharp, this edge round". More than our 32×32 pictures need now; worth it for larger art. |

### D2. Drawing the depth by hand (the interface question)

- **Depth painting** (Kang 1998, with a US patent): paint depth onto a single image while **side views update live
  beside it**. That is the design our window now has: draw on the sprite, and the model is made again when the button
  is let go.
- **Image-based modelling and photo editing** (Oh, Chen, Dorsey, Durand, SIGGRAPH 2001): brushes that **set** a
  depth, or **add or take away** from it ("chiselling"), and a relative brush that sets one part's depth from
  another's. Our Thinner / Thicker brushes are the add-or-take-away kind; Keep sets a pixel back to as made.
- **Hill and valley brushes** (Adobe, US 8,665,258): the brush paints *curvature*, not height, and a solver spreads it
  smoothly. Painting curvature gives smooth results from rough strokes; painting height (what we do) gives exact
  pixel control, which suits pixel art better.
- **Stroke-based depth maps** (Gerrits et al. 2011) and **depth (in)equalities for cartoons** (Sýkora et al.,
  Eurographics 2010): scribbles that only say "this is in front of that", and an optimiser finds depths that obey
  them. Useful if we ever model overlapping parts (a hand round a hilt).
- **Ink-and-Ray** (Sýkora et al., TOG 2014) and **high-relief models from drawings** (Dvorožňák et al. 2018): split
  the drawing into parts, inflate each with a Poisson solve, then stitch them along shared edges. **Monster Mash**
  (Dvorožňák et al., SIGGRAPH Asia 2020; open source) adds a rigidity-keeping deformation (ARAP-L) so the parts can
  be animated. Our parts picture plays the same role as their part split.
- **SmoothSketch** (Karpenko, Hughes 2006): outlines with hidden parts (cusps, T-junctions) are completed first,
  then made smooth. Relevant for sprites where one part hides another.

### D3. Lighting flat art without making a model

- **Lumo** (Johnston, NPAR 2002): at an outline the surface normal lies flat in the picture, so the normal there is
  the outline's own direction; normals inside are filled in smoothly (Nx and Ny interpolated, Nz worked out again).
  This gives lighting on a flat sprite with no model at all.
- **Normal maps for pixel art** (a survey, arXiv 2212.09692; Laigter's own notes): height from a distance transform
  (a bevel from the outline) plus the picture's brightness, then normals by derivative filters. This is how the
  game's wall relief maps were made. A dark pixel in pixel art is an outline or a shadow, not a hollow, so
  brightness-as-height misleads on sprites; the outline bevel is the safer half.

### D4. The plain mesh side

- **Minecraft-style extrusion** (unitycoder's ExtrudeSprite gist; 0fps "Meshing in a Minecraft game"): a front quad,
  a back quad, and a side quad wherever an opaque pixel borders a clear one; greedy merging of side quads cuts the
  count. Our "Flat" depth is this.
- **Exact Euclidean distance transform in linear time** (Felzenszwalb, Huttenlocher, Theory of Computing 2012): two
  passes of a one-dimensional lower-envelope-of-parabolas algorithm. Our `distance_out` compares every pixel with
  every clear pixel, which is fine at 32×32 but slow at 256×256; this is the drop-in replacement if larger art comes.

### D5. What was built from this today

1. **Handle width: Coloured middle** (the new default, `--handle inner`): a shaft's or grip's dark outline is left off
   the model, so the handle is as wide as its coloured pixels, the width the eye reads in the original. On the three
   axes this took the handle from 4 sprite pixels across to 2, and each model is still closed
   (`work\weapon3d\show-handle-1.png`). This is the medial-axis view: the radius comes from the coloured part.
2. **Drawing on the sprite** (the window's *Draw on it*, or `--paint FILE.png`): a grey picture over the sprite.
   Grey 128 is as made, darker is thinner (64 half), lighter is thicker (255 twice), black cuts the pixel away. It is
   painting height directly, in the Kang / Oh style, with the model made again after each stroke.

### D6. Worth building next (not started)

1. A **Poisson inflation** depth (Baran–Lehtinen, z = √h) as a fifth Depth choice, with the painted grey as the
   right-hand side, giving smooth thickness changes from rough painting instead of steps.
2. **Puffball / medial-axis radius** for shafts and grips, so slanted handles are round without standing the sprite
   upright, and the painted grey scales the radius (wider or narrower), not only the depth.
3. A **Profile** row (round, bevel, flat) from the Oswald exponent.
4. The **linear-time distance transform**, for sprites larger than 64×64.

### D7. A finer model than the sprite's pixels (built 2026-11-18, `--detail N`)

More reading for this step: **Depixelizing pixel art** (Kopf, Lischinski, SIGGRAPH 2011: a similarity graph of the
pixels, cells reshaped so diagonal neighbours touch, then B-spline outlines with their curvature smoothed), the pixel-art
enlargers that keep the palette (**MMPX**, McGuire and Gagiu, JCGT 2021; **cleanEdge**, torcado 2022; ScaleFX; xBR
blends new colours, so it was ruled out), and **quadric error simplification** (Garland, Heckbert, SIGGRAPH 1997) for
cutting the face count later.

What was built: the outline painted over, the sprite enlarged N times by cleanEdge (we already had a Python port from
the upright-sprite work; it keeps every colour and smooths slopes and curves, which is the part of Kopf–Lischinski we
need, without vectors), then Baran–Lehtinen inflation (lap h = −4, solved by matrix-free conjugate gradients, the parts
coupled without walls between them) for the depth, part by part: sqrt(h/2) for shafts and grips (a true circle across
a strip), a lens for blades and axe heads, a bar for guards. Also from section D: the exact linear-time distance
transform (Felzenszwalb–Huttenlocher) now replaces the old every-pixel-against-every-pixel one (the same results to the
last digit, `work\weapon3d\test_edt.py`).

Results (`work\fine\show-fine-2.png`, `show-closeup-1.png`): at 4x the outlines, axe edges, sword tips and handles are
smooth and round where 1x has steps; every model closed; 2 to 3 s and 7,000 to 13,000 faces. 8x adds nothing visible.
Still open: black pixels inside the sprite (gap lines, a guard's middle) stay black and read as small holes; cleanEdge
rounds a stepped guard end into a curve; the face count could come down a lot with quadric simplification of the flat
areas.

New sources: [Depixelizing pixel art](https://johanneskopf.de/publications/pixelart/paper/pixel.pdf),
[MMPX](https://jcgt.org/published/0010/02/04/paper.pdf), [cleanEdge](https://torcado.com/blog/cleanEdge/),
[pixel-art scaler comparison](https://github.com/Azq2/ra-pixelart-scale),
[Quadric error simplification (Garland, Heckbert 1997)](https://people.eecs.berkeley.edu/~jrs/meshpapers/GarlandHeckbert2.pdf),
[Optimal triangulation and quadric simplification](http://mgarland.org/files/papers/qtheory.pdf)

### D8. Few polygons (built 2026-11-18, `--mesh lowpoly`, the default)

The user's rule: "these 3d models should be hardly any polygons. The handle could be made out of 20 polygons." The
key point: the colour does not need faces. With the sprite as a texture laid on from the front (planar UVs, nearest
pixel), every pixel still shows exactly, and the geometry only has to give the shape. So each part is built as the
simplest closed shape the literature uses for it: a handle is a generalized cylinder (Gingold et al. 2009; 3-Sweep,
Chen et al. 2013) with six sides and one ring wherever its width changes (rows kept by Douglas–Peucker); a blade is
the classic diamond section swept along its outline; a head or guard is a plate from the traced outline (simplified by
Douglas–Peucker), its edge sharp, an inset bevel (mitred offset) up to a flat face, triangulated by ear clipping.
Results (`work\fine\show-lowpoly-1.png`): handles 20 triangles each, swords 94 to 206, axes 154 to 166, all parts
closed; from the front they look almost the same as the 10,000-face models. Not done: welding the parts into one mesh
(they touch); a bevel can fail on a very thin plate, which then becomes a slab with straight sides.

### D sources

[Teddy (Igarashi et al. 1999)](https://www.cs.toronto.edu/~jacobson/seminar/igarashi-et-al-1999.pdf),
[Teddy project page](https://www-ui.is.s.u-tokyo.ac.jp/~takeo/research/teddy/teddy.htm),
[Variational implicit sketching (MERL TR2002-27)](https://www.merl.com/publications/docs/TR2002-27.pdf),
[Notes on inflating curves (Baran, Lehtinen 2009)](https://alecjacobson.com/weblog/media/notes-on-inflating-curves-2009-baran.pdf),
[Jacobson's note on it](https://www.alecjacobson.com/weblog/4613.html),
[Differential Walk on Spheres](https://arxiv.org/html/2405.12964v4),
[Puffball (Twarog et al. 2012)](https://persci.mit.edu/pub_pdfs/twarog-sap-2012.pdf),
[Segmenting 2D shapes using 3D inflation](https://www.researchgate.net/publication/275436395_Segmenting_2D_Shapes_using_3D_Inflation),
[Convolution surfaces from silhouettes (Tai et al. 2004)](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-8659.2004.00006.x),
[Structured annotations (Gingold et al. 2009)](https://cims.nyu.edu/gcl/papers/gingold2009sa2.pdf),
[Structured annotations code](https://github.com/yig/StructuredAnnotations),
[3-Sweep (Chen et al. 2013)](https://cg.cs.tsinghua.edu.cn/papers/SIGASIA-2013-3sweep.pdf),
[Sketch-based modeling with few strokes (Cherlin et al. 2005)](https://giv.cpsc.ucalgary.ca/pdf/sbm-sccg2005-cherlin.pdf),
[Oswald's thesis, convex single-view reconstruction](https://mediatum.ub.tum.de/doc/1160069/1160069.pdf),
[Silhouette-based variational methods (Töppe et al.)](https://link.springer.com/chapter/10.1007/978-3-642-24870-2_5),
[Fast and controllable modelling from silhouettes (Prasad et al. 2005)](https://www.robots.ox.ac.uk/~vgg/publications/2005/Prasad05/prasad05.pdf),
[Repoussé (Joshi, Carr 2008)](https://diglib.eg.org/handle/10.2312/SBM.SBM08.049-055),
[FiberMesh (Nealen et al. 2007)](https://igl.ethz.ch/projects/FiberMesh/fibermesh.pdf),
[Freeform vector graphics with thin-plate splines](https://hhoppe.com/freeform.pdf),
[Depth painting (Kang 1998)](https://www.researchgate.net/publication/2860277_Depth_Painting_for_Image-Based_Rendering_Applications),
[Depth painting patent](https://patents.google.com/patent/US6417850B1/en),
[Stroke-based depth maps](https://www.researchgate.net/publication/224257555_Stroke-based_Creation_of_Depth_Maps),
[Adding depth to cartoons (Sýkora et al. 2010)](https://www.academia.edu/33950751/Adding_Depth_to_Cartoons_Using_Sparse_Depth_In_equalities),
[Ink-and-Ray (Sýkora et al. 2014)](https://users.cs.utah.edu/~ladislav/sykora14ink/sykora14ink.html),
[High-relief models from drawings (Dvorožňák et al. 2018)](https://users.cs.utah.edu/~ladislav/dvoroznak18seamless/dvoroznak18seamless.pdf),
[Monster Mash](https://igl.ethz.ch/projects/monster-mash/), [Monster Mash code](https://github.com/google/monster-mash),
[SmoothSketch (Karpenko, Hughes 2006)](https://cs.brown.edu/people/jhughes/papers/Karpenko-S3F-2006/main.htm),
[RigMesh (Borosán et al. 2012)](https://game.engineering.nyu.edu/rigmesh/),
[Lumo (Johnston 2002)](https://dl.acm.org/citation.cfm?id=508538),
[Normal map generation for pixel art (survey)](https://arxiv.org/pdf/2212.09692),
[Laigter](https://azagaya.itch.io/laigter),
[Normal maps from the sprite's outline](https://www.spritecook.ai/blog/pixel-art-normal-maps-from-outline),
[Voxify3D](https://arxiv.org/abs/2512.07834), [Pixal3D](https://arxiv.org/pdf/2605.10922),
[ExtrudeSprite gist](https://gist.github.com/unitycoder/6985a2ab030dcff42050ea7ebed53726),
[Meshing in a Minecraft game (0fps)](https://0fps.net/2012/06/30/meshing-in-a-minecraft-game/),
[Distance transforms of sampled functions (Felzenszwalb, Huttenlocher)](https://cs.brown.edu/people/pfelzens/papers/dt-final.pdf)

## E. A sword built like a real sword (2026-11-18, late)

The user: "take a look at a real sword and other sword models to see how to make one ... do a lot of research on new
scientific papers and old ones too". What a real one-handed sword measures, what game modellers do, what the papers
say, and what was built from it.

### E1. What a real sword measures

Figures from measured originals and close replicas (Type XII and near it, the knightly one-handed sword):

| Part | Measured | As a share |
| --- | --- | --- |
| Blade length | 74 to 82 cm | hilt to blade 1:5 to 1:7 (Johnsson's analyses) |
| Blade width at the guard | 50 to 54 mm, narrowing to about half | |
| Blade thickness at the guard | 4.8 to 6 mm (Albion Knight 4.8 to 4.9; general 6 to 9) | about a tenth of the width |
| Blade thickness at the tip | 1.9 to 3 mm (Albion Knight 1.88 an inch from the tip) | 35 to 40 % of the base: the *distal taper* |
| Grip | 108 to 114 mm long; a flattened oval (38 x 34 mm measured on a two-hander) | wider than thick |
| Guard | 165 to 200 mm across; a bar 8 x 9 to 10 mm, 17 mm where the blade passes | three to four blade widths across; thinner than the grip |
| Pommel | a disc 45 to 54 mm across, 26 to 29 mm thick | wider than the grip; a little over half as thick as wide |

Cross-sections: lenticular (a lens, early), diamond (four flats and a ridge, later, stiffer), hollow-ground diamond,
hexagonal; a fuller is a groove that lightens the blade. Weights of one blade in six sections: hollow ground 462 g,
diamond with fuller 560 g, diamond 600 g, lens with fuller 671 g, lens 798 g, hexagonal 1082 g. Distal taper may be
continuous, in steps, or only in the latter half; a replica without it handles like a bar. Peter Johnsson's work
suggests medieval swords were laid out with circles and polygons (pommel and guard a third of the hilt, blade a
quarter of the basic circle wide), most plainly in the 12th and 13th centuries.

### E2. What game modellers do

Low-poly swords in asset packs run 100 to 4,500 triangles, usually 200 to 1,500; ours are 94 to 300. Tutorials build
the blade as a plane with one centre loop pulled out (the diamond section), the guard as a box with a centre loop and
tapered ends, the handle a cylinder, the pommel a short cylinder or ball; triangles are fine on a rigid prop; the
pivot sits on the grip. A faceted bevel on the blade is what makes the edge read at a low count. The Volcano sword
generator (Pirovano, Mainetti, Loiacono 2015) describes any sword by a few curves and lengths a part (blade, guard,
grip, pommel), which is what our parts and their settings amount to.

### E3. What the papers add

- **Part by part, each a simple primitive** is where the literature has landed again: 3-Sweep (2013) and its
  automatic follow-up AutoSweep (2020) build man-made things from generalized cylinders and cuboids;
  PrimitiveAnything (SIGGRAPH 2025) and Light-SQ (SIGGRAPH Asia 2025) learn to break a shape into primitives the way a
  person would. Our parts picture with a shape a part is the same idea, done by hand and by rules.
- **Symmetry as the missing information**: Reflect3D ("Symmetry Strikes Back", 2024) finds the mirror plane in one
  picture and uses it to fix the unseen back. A sprite's back is its front mirrored, which is what we build.
- **Inverse procedural modelling** (Garifullin et al. 2024): fit the parameters of a procedural generator to one
  picture. A sword generator whose few numbers (blade width, taper, guard span, pommel size) are read off the sprite
  is exactly that, with the sprite's rows as the measurement.
- **Extreme simplification keeps the silhouette**: Low-poly Mesh Generation for Building Models (Gao et al. 2022)
  and its follow-up for general models start from the visual hull (the silhouettes) and judge by how the result
  looks, not by distance. We already keep the traced outline and spend no faces on colour.
- Voxify3D (2025/26) goes the other way (a mesh into pixel-art voxels with six orthographic views and a fixed
  palette); its lesson for us is orthographic views and palette colours only, which we have.

### E4. What was built from it (lowpoly.py, regions.py, sprite3d.py)

A weapon with a blade part is now built to a sword's proportions (constants at `build_regions` in lowpoly.py):

| Rule | Value | Real |
| --- | --- | --- |
| `BLADE_THICK`: blade thickness from its own width | a quarter of the width | a tenth (doubled and more so it reads at game size) |
| `DISTAL`: thickness at the tip against the guard end | 0.4, falling evenly along the blade | 0.35 to 0.4 |
| `GRIP_OVAL`: grip thickness against its width | 0.75 | 0.75 to 0.9 |
| `GUARD_OF_HANDLE`: the guard against the grip's thickness | 1.1, whatever the thickness setting | about 0.5 to 0.8 (kept thicker: it must not hide behind the grip) |
| `POMMEL_DISC`: pommel thickness against its width | 0.6, never thinner than the grip | 0.55 |

Also: the pommel is found by the guess (the rows at the foot of the grip in another colour than the grip's upper
half, or plainly wider; `regions.pommel`) and built as a disc; the grip's thickness is taken from its usual row, not
its widest; the blade's own colours running through the guard's top row stay blade (the guard's top was painted
steel); a small pommel cap is 20 triangles and a guard's outline is simplified harder. The thickness setting is now
only a ceiling for the blade. Sheets: `work\dbg010\real\cmp2.png`, `work\dbg010\real\set\set2.png`.

Not built: a fuller as geometry (it is in the texture); guard arms that thin toward their ends; hexagonal or
hollow-ground sections as a choice; a rule for axes and maces from real ones (haft oval, head a wedge).

### E sources

[Understanding blade properties (myArmoury)](https://myarmoury.com/feature_properties.html),
[Sword construction and blade geometry (Arthwys)](https://www.arthwys.com/p/sword-construction-and-blade-geometry),
[Blade geometry (Wikipedia)](https://en.wikipedia.org/wiki/Blade_geometry),
[Oakeshott typology (Wikipedia)](https://en.wikipedia.org/wiki/Oakeshott_typology),
[Oakeshott's typology (Albion)](https://albion-swords.com/articles/oakeshott-typology.htm),
[Type XII swords (myArmoury)](https://myarmoury.com/feature_spotxii.html),
[Albion Knight review (myArmoury)](https://myarmoury.com/review_alb_knight.php),
[Albion Knight owner's measurements (SBG forum)](https://sbg-sword-forum.forums.net/thread/62922/albion-knight-sword-review),
[The Knight (Albion)](https://albion-swords.com/product/the-knight/),
[Castle Keep Type XII review](https://myarmoury.com/review_ck_xii.html),
[Szczerbiec](https://en.wikipedia.org/wiki/Szczerbiec),
[Historical Swiss swords examined (ARMA)](https://thearma.org/spotlight/swiss-swords.html),
[The River Thames sword (myArmoury)](https://myarmoury.com/feature_thames.html),
[Bronze Anglo-Saxon sword pommels](https://sagy.vikingove.cz/en/bronze-anglo-saxon-sword-pommels/),
[Design and geometry (Peter Johnsson)](https://swordreflections.com/notebook/design-geometry/),
[The Søborg sword (Peter Johnsson)](https://swordreflections.com/notes/the-soborg-sword/),
[Low poly sword notes (lowpoly3d)](http://lowpoly3d.com/en/models/low-poly-sword),
[Low-poly swords and daggers (StationSupply)](https://stationsupply.itch.io/low-poly-swords-and-daggers),
[Swords pack (Pure Poly)](https://pure-poly.artstation.com/store/DkzD/swords-pack-1-300-low-poly-weapons),
[Volcano: an interactive sword generator](https://www.semanticscholar.org/paper/Volcano:-An-interactive-sword-generator-Pirovano-Mainetti/d7e07d261efc0afb491aadd237bfc152f544af97),
[3-Sweep in CACM](https://cacm.acm.org/research/extracting-3d-objects-from-photographs-using-3-sweep/),
[AutoSweep](https://arxiv.org/pdf/2005.13312),
[PrimitiveAnything](https://arxiv.org/abs/2505.04622), [Light-SQ](https://arxiv.org/pdf/2509.24986),
[Symmetry Strikes Back (Reflect3D)](https://arxiv.org/pdf/2411.17763),
[Single-view reconstruction by inverse procedural modelling](https://arxiv.org/pdf/2310.13373),
[Low-poly mesh generation for building models](https://dl.acm.org/doi/fullHtml/10.1145/3528233.3530716),
[RigMesh paper](https://www.cs.columbia.edu/cg/pdfs/198-rigmesh.pdf)
