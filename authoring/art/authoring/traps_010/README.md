# Scratch stake trap art, 0.1.0

`stake_thicket` is the compact broken-crescent visual for
`vn_building_bambo_outpost_chi`. `stake_fan` is the broader, lower asymmetric
visual for `vn_building_defense_outpost_bambo_chi`.

Both sources are packed editable Blender files with one neutral opaque 512px
hardwood/earth/foliage atlas and retained source PNGs. The native owner markers
remain integration-owned. No player colour is baked into the wood. All leaf
blades are closed solid geometry; there are no alpha cards or terrain holes.

The medieval timber motif is informed by the Bach Dang stake-yard description in
the [UNESCO nomination management plan](https://whc.unesco.org/document/211490),
PDF pages 38-39. These compact infantry compositions are artistic extrapolations,
not reconstructions of documented portable devices. No gameplay, mechanics,
icons, names, project identities, or native lifecycle records are authored here.

Rebuild from the Garrison root only after `tools/verify_workspace.py --storage-only`
passes. Use the approved task-owned Blender executable with
`--background --factory-startup --python tools/release_010/trap_build.py --
stake_thicket 6.4`, then repeat with `stake_fan 20.8`. Run
`tools/release_010/trap_freeze.py` using the configured Python after successful
Blender completion. The recipe and small common runner are the durable source.
Do not run a native cook here: release integration owns its serialized cook token.

The native animator scales remain 75% and 25%, respectively: 6.4 and 20.8 source
widths produce expected final widths 4.8 and 5.2. Both source bounds are centered
in XY with ground at Z=0. The two FBX parts use explicit stages: earth/limited
foliage at 0, hardwood at 5. Garrison's English-house building profile is solely
the geometry compiler carrier; its generated actors must not replace Vietnam actors.

`art/recipes/release_010/traps_010.json` freezes source/export hashes and metadata.
`output/release_010/traps/<asset>/validation.json` records Garrison preflight,
closed-mesh/UV/material checks and ray-cast base/earth contact. The same output
directory retains game-angle, close, top, front, back, left, right and bottom
colour renders. Source/export proof does not establish native appearance,
construction/repair/death behavior, owner colour, import, or multiplayer success.
