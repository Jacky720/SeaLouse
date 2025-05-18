# SeaLouse
This is a Blender plugin to import and export the KMS (in-game model), EVM (cutscene model), and CMDL (a supplement to the other two) formats in Metal Gear Solid 2: Sons of Liberty, preferably for the Master Collection (CMDL is only present on the Master Collection version of the game, but it appears people know how to edit textures there more easily anyway so it's fine).

## How to install
Click the green "Code" button and "Download ZIP". Then, in Blender, go to Edit > Preferences > Add-ons > Install and select the zip file. It should be immediately added to your File > Import and File > Export menus.

## How to use
There are still several restrictions on how the exporter works, so I'll go over those, and the recommended workarounds, for both file types.

KMS:
1. Each KMS model is split into several meshes, which are split into several vertex groups. Meshes are separated as Blender meshes. Vertex groups are separated as Blender materials, even though it's possible for two vertex groups (even on the same mesh) to have the same textures. 
2. KMS has a limit of two bone weights per vertex, and they must specifically be the bone corresponding to the current mesh and its parent. The Object > SeaLouse > Split by bone option will attempt to automatically split your selected mesh accordingly, which you can then join to the MGS2 model to match transformations.
3. Materials are exported based on primarily their node tree, accessing nodes by name to check their texture ID, but if that fails the exporter will fall back on "colorMapFallback", "specularMapFallback", and "environmentMapFallback" custom properties. You can add these to your custom materials, since they likely won't have the same node structure as MGS2 materials. There is also a "flag" custom property, which I've set to default to 760 on the first mesh and 761 on all other meshes. I don't really know what it does, but if they're all 760 the weights act weird.

EVM:
1. For EVM models, it's all one mesh, but still split into vertex groups. It's recommended to join your custom model so that it resembles the mesh structure of the model you're editing; more on that later.
2. EVM has a limit of four bone weights per vertex, but also a limit of 8 bone weights per vertex group (recall, a vertex group is a material). You can split off a region of geometry that you know contains 8 bone weights or less, and click the number next to the material on the resulting split mesh to create a single-user copy and ensure it will remain a separate material when re-joining.
3. EVM materials are exactly the same with regards to texture IDs. The flag value instead defaults to 760 if the material uses only one weight and 72 otherwise.

Both the KMS and EVM exporters also strictly require all geometry be triangulated and have no loose ends or unused materials. I use the Nier2Blender2Nier "Delete Loose Geometry (All)" option to ensure I've cleaned up all stray vertices and edges.

Besides that... I think most of the CMDL code could work for MGS3, but I don't have the main MDL for that game handled at all. Some models seem to have a lower vertex limit in modification than others, be careful. The exporter may alter the normals, even if a model is re-exported with no changes. If something doesn't seem to work, try exporting with no changes and then apply modifications piecemeal until you can identify the issue.

Possible bugs to watch for:
- An unending load screen is a sign of a corrupt CMDL.
- A game crash on rendering the model is a sign of either unused materials (remember to delete materials that only applied to the original model and not the custom one) or too many vertices.
- Corrupted UV maps occur due to the CMDL exporter not splitting along UV seams. You should split your UV seams before export. Do not use the tantalizing "split CMDL faces" checkbox, it doesn't work, especially on KMS.

Have fun!
