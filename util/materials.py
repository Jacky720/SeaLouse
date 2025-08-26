import bpy
import os
from math import radians
from ..ctxr.ctxr import DDS, CTXR, ctxr_lookup_path
from .util import replaceExt, stripAllExt

class MaterialHelper:
    material: bpy.types.Material
    node_tree: bpy.types.NodeTree
    nodes: bpy.types.Nodes
    links: bpy.types.NodeLinks
    
    def __init__(self, material: bpy.types.Material):
        self.material = material
        if not material.use_nodes or material.node_tree is None:
            # Enable Nodes
            material.use_nodes = True
            # Clear Nodes and Links
            material.node_tree.links.clear()
            material.node_tree.nodes.clear()
        self.node_tree = material.node_tree
        self.nodes = self.node_tree.nodes
        self.links = self.node_tree.links
    
    def make_alpha_multiplier(self, image_node: bpy.types.Node, name: str = 'Multiply Alpha') -> bpy.types.Node:
        alpha_multiplier = self.nodes.new(type='ShaderNodeMath')
        alpha_multiplier.label = name
        alpha_multiplier.name = name
        alpha_multiplier.location = (image_node.location[0] + 300, image_node.location[1])
        alpha_multiplier.operation = 'MULTIPLY'
        alpha_multiplier.inputs[1].default_value = 2.0
        self.links.new(image_node.outputs['Alpha'], alpha_multiplier.inputs[0])
        alpha_multiplier.hide = True
        return alpha_multiplier

    def make_specular_env_multiplier(self, env_node: bpy.types.Node, specular_output: bpy.types.NodeSocket) -> bpy.types.Node:
        env_multiplier = self.nodes.new(type='ShaderNodeMix')
        env_multiplier.name = 'Multiply EnvMap'
        env_multiplier.label = 'Multiply EnvMap'
        specular_node = specular_output.node  # Give this some space on the x-axis
        env_multiplier.location = (specular_node.location[0] + 300, env_node.location[1])
        env_multiplier.hide = True
        
        env_multiplier.data_type = "RGBA"
        env_multiplier.blend_type = 'MULTIPLY'
        env_multiplier.inputs['Factor'].default_value = 1.0
        self.links.new(specular_output, env_multiplier.inputs[6])  # 'A'
        self.links.new(env_node.outputs['Color'], env_multiplier.inputs[7])  # 'B'
        return env_multiplier
    
    @staticmethod
    def get_unique_id(flag: int, colorId: int, specularId: int, environmentId: int) -> str:
        return str(flag)+str(colorId)+str(specularId)+str(specularId)


class TextureLoad:
    extract_dir: str
    ctxr_dir: str | None  # ctxr load folder if using ctxr
    ctxr_name_lookup: dict
    material_cache: dict
    overwrite_existing: bool

    def __init__(self, extract_dir: str, ctxr_dir: str = None, overwrite_existing: bool = False):
        self.extract_dir = extract_dir
        self.ctxr_dir = ctxr_dir
        self.material_cache = {}
        self.ctxr_name_lookup = {}
        self.overwrite_existing = overwrite_existing

        # Load dictionary regardless, we'll use it to guess texture blending modes
        with open(ctxr_lookup_path, "rt") as f:
            for line in f.readlines():
                tga_num = os.path.splitext(line.split()[1])[0]
                self.ctxr_name_lookup[int(tga_num)] = line.split()[2]
    
    def get_texture(self, mapID: int) -> bpy.types.Image | None:
        mapName = self.get_texture_nice_name(mapID) if self.ctxr_dir else self.get_texture_tri_name(mapID)
        if mapName == "":
            return None
        if mapName.endswith(".png"):
            mapName = replaceExt(mapName, "dds")
        
        if bpy.data.images.get(mapName) is not None:
            return bpy.data.images.get(mapName)
        
        mapPath = os.path.join(self.extract_dir, mapName)
        
        if not os.path.exists(mapPath) or self.overwrite_existing:
            if not self.ctxr_dir:
                print("Path did not exist:", mapPath)
                return None
            # Load ctxr
            ctxr_path = os.path.join(self.ctxr_dir, replaceExt(mapName, "ctxr"))
            if not os.path.exists(ctxr_path):
                return None
            print("Extracting", ctxr_path, "to DDS")
            ctxr = CTXR()
            with open(ctxr_path, "rb") as f:
                ctxr.fromFile(f)
            dds = ctxr.convertDDS()
            with open(mapPath, "wb") as f:
                dds.writeToFile(f)
        
        bpy.data.images.load(mapPath)
        return bpy.data.images.get(mapName)
    
    def get_texture_nice_name(self, mapID: int) -> str:
        mapName = self.get_texture_tri_name(mapID)
        if mapID != 0 and mapID in self.ctxr_name_lookup:
            mapName = self.ctxr_name_lookup[mapID]
        return mapName
    
    @staticmethod
    def get_texture_tri_name(mapID: int) -> str:
        if mapID == 0:
            return ""
        return f"{mapID}.tga"


    def makeMaterial(self, name: str, flag: int, colorId: int, specularId: int, environmentId: int, merge_materials: bool) -> bpy.types.Material:
        unique_id = MaterialHelper.get_unique_id(flag, colorId, specularId, environmentId)

        if merge_materials and unique_id in self.material_cache:
            return self.material_cache[unique_id]

        colorMapName = self.get_texture_nice_name(colorId)
        material = bpy.data.materials.new(stripAllExt(colorMapName))
        self.material_cache[unique_id] = material
        matHelper = MaterialHelper(material)
        # Save flag as custom property
        material["flag"] = flag
        # Recreate Nodes and Links with references
        nodes = matHelper.nodes
        links = matHelper.links
        # Render properties
        # These two could be exposed as user-defined properties
        material.blend_method = 'HASHED'
        material.use_backface_culling = True
        # PrincipledBSDF and Ouput Shader
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = 1200,0
        principled = nodes.new(type='ShaderNodeBsdfPrincipled')
        principled.location = 900,0
        output_link = links.new( principled.outputs['BSDF'], output.inputs['Surface'] )

        colorMap = self.get_texture(colorId)
        isAlphaBlended = colorMap is not None and colorMapName.find("alp") >= 0 and colorMapName.find("ovl") >= 0
        if colorMap is not None:
            color_image = nodes.new(type='ShaderNodeTexImage')
            color_image.location = 0,0
            color_image.image = colorMap
            colorMap.colorspace_settings.name = 'sRGB'
            # If alpha output is disconnected, the RGB values will be multiplied by it 
            # unless alpha_mode is set to "CHANNEL_PACKED"
            colorMap.alpha_mode = "CHANNEL_PACKED"
            color_image.hide = True
            color_image.name = "g_ColorMap"
            color_image.label = "g_ColorMap"
            links.new(color_image.outputs['Color'], principled.inputs['Base Color'])
            
            if isAlphaBlended:
                output_alpha = color_image.outputs['Alpha']
                if self.ctxr_dir:
                    output_alpha = matHelper.make_alpha_multiplier(color_image).outputs[0]
                links.new(output_alpha, principled.inputs['Alpha'])
                
        elif colorId > 0:
            material["colorMapFallback"] = colorId
        
        specularMap = self.get_texture(specularId)
        specularOut = None
        if specularMap is not None:
            specular_image = nodes.new(type='ShaderNodeTexImage')
            specular_image.location = 0,-60
            specular_image.image = specularMap
            specularMap.colorspace_settings.name = 'Non-Color'
            specular_image.hide = True
            specular_image.name = "g_SpecularMap"
            specular_image.label = "g_SpecularMap"
            specularOut = specular_image.outputs['Alpha']

            if self.ctxr_dir:
                specular_mul_node = matHelper.make_alpha_multiplier(specular_image, "Specular Alpha Multiplier")
                specularOut = specular_mul_node.outputs[0]
                
            if 'Specular' in principled.inputs:
                links.new(specularOut, principled.inputs['Specular'])
            else:
                links.new(specularOut, principled.inputs['Specular IOR Level'])
        elif specularId > 0:
            material["specularMapFallback"] = specularId
        
        if 'Specular' in principled.inputs:
            principled.inputs['Specular'].default_value = 0.0
        else:
            principled.inputs['Specular IOR Level'].default_value = 0.0
        
        envMap = self.get_texture(environmentId)
        if envMap is not None:
            # If alpha output is disconnected, the RGB values will be multiplied by it 
            # unless alpha_mode is set to "CHANNEL_PACKED"
            envMap.alpha_mode = "CHANNEL_PACKED"
            
            env_uv = nodes.new(type='ShaderNodeTexCoord')
            env_uv.location = -320,-120
            env_uv.hide = True
            
            env_mapping = nodes.new(type='ShaderNodeMapping')
            env_mapping.location = -160,-120
            env_mapping.inputs['Rotation'].default_value[2] = radians(90)
            env_mapping.hide = True
            
            env_image = nodes.new(type='ShaderNodeTexEnvironment')
            env_image.location = 0,-120
            env_image.image = envMap
            # Environment maps are supposed to contain colors
            # if envMap != colorMap:
            #     envMap.colorspace_settings.name = 'Non-Color'
            env_image.hide = True
            env_image.name = "g_EnvironmentMap"
            env_image.label = "g_EnvironmentMap"
            environmentOut = env_image.outputs['Color']
            
            links.new(env_uv.outputs['Reflection'], env_mapping.inputs['Vector'])
            links.new(env_mapping.outputs['Vector'], env_image.inputs['Vector'])

            # Truer to the PS2 look, environment maps are rendered as an additive pass
            
            if specularMap is not None:
                env_mul = matHelper.make_specular_env_multiplier(env_image, specularOut)
                environmentOut = env_mul.outputs[2]  # Color Result
            
            if 'Emission Color' in principled.inputs:
                links.new(environmentOut, principled.inputs['Emission Color'])
            else:
                links.new(environmentOut, principled.inputs['Emission'])
            
            
            principled.inputs['Emission Strength'].default_value = 1.0
            
            # output_alpha = env_image.outputs['Alpha']
            # if self.ctxr_dir:
            #     output_alpha = matHelper.make_alpha_multiplier(env_image).outputs[0]
            # links.new(output_alpha, principled.inputs['Metallic'])
        elif environmentId > 0:
            material["environmentMapFallback"] = environmentId
        
        return material


class TextureSave:
    ctxr_id_lookup: dict
    textures_to_save: set[bpy.types.Image]

    def __init__(self):
        self.ctxr_id_lookup = {}
        self.textures_to_save = set()
        
        with open(ctxr_lookup_path, "rt") as f:
            for line in f.readlines():
                tga_num = os.path.splitext(line.split()[1])[0]
                self.ctxr_id_lookup[line.split()[2]] = int(tga_num)
    
    def get_map(self, mat: bpy.types.Material, mapType: str) -> int:
        nodes = mat.node_tree.nodes
        mapType = mapType.lower()
        if "map" not in mapType:
            mapType += "Map"
        mapType = mapType.replace("map", "Map")
        
        mapID = 0
        matchImage = None
        
        if nodes.get(f"g_{mapType.capitalize()}") is not None:
            matchImage = nodes[f"g_{mapType.capitalize()}"].image
        elif mat.get(f"{mapType}Fallback") is not None:
            mapID = mat[f"{mapType}Fallback"]
        if not matchImage and "Principled BSDF" in nodes:  # Check anything
            principled = nodes["Principled BSDF"]
            if mapType == 'colorMap':
                inputName = "Base Color"
            elif mapType == 'specularMap':
                if "Specular" in principled.inputs:
                    inputName = "Specular"
                else:
                    inputName = "Specular IOR Level"
            elif mapType == 'environmentMap':
                if "Emission" in principled.inputs:
                    inputName = "Emission"
                else:
                    inputName = "Emission Color"
            else:
                return mapID
            
            if len(principled.inputs[inputName].links) != 1:
                return mapID
            fromNode = principled.inputs[inputName].links[0].from_node
            if fromNode.bl_idname == 'ShaderNodeTexImage':
                matchImage = fromNode.image
            elif fromNode.bl_idname == 'ShaderNodeMath' and len(fromNode.inputs[0].links) == 1:
                matchImage = fromNode.inputs[0].links[0].from_node.image
            elif fromNode.bl_idname == 'ShaderNodeMix' and len(fromNode.inputs[7].links) == 1 and \
              fromNode.inputs[7].links[0].from_node.bl_idname == 'ShaderNodeTexImage':
                matchImage = fromNode.inputs[7].links[0].from_node.image
                # Also consider swapping A and B inputs (very unlikely, but not hard to cover our bases)
            elif fromNode.bl_idname == 'ShaderNodeMix' and len(fromNode.inputs[6].links) == 1 and \
              fromNode.inputs[6].links[0].from_node.bl_idname == 'ShaderNodeTexImage':
                matchImage = fromNode.inputs[6].links[0].from_node.image
            else:
                return mapID
        
        if matchImage is not None:
            matchImageName, matchImageExt = os.path.splitext(matchImage.name)
            # TGA detection takes priority over fallback ID
            if matchImageName.isnumeric() and matchImageExt == ".tga":
                mapID = int(matchImageName)
            elif matchImageExt == ".dds" and matchImageName + ".png" in self.ctxr_id_lookup:
                self.textures_to_save.add(matchImage)
                # DDS detection does not have priority over fallback ID
                if not mapID:
                    mapID = self.ctxr_id_lookup[matchImageName + ".png"]
        
        return mapID
    
    def save_textures(self, extract_dir: str):
        for image in self.textures_to_save:
            ctxr_name = replaceExt(image.name, "ctxr")
            print("Packing image", ctxr_name)
            if not os.path.exists(image.filepath_from_user()):
                print("Error: Could not locate image on disk, skipping.")
                continue
            with open(image.filepath_from_user(), "rb") as f:
                dds = DDS().fromFile(f)
            ctxr = dds.convertCTXR()
            if "ovl" in ctxr_name and "alp" in ctxr_name:
                # Specular maps/transparent textures need different parameters
                ctxr.header.unknown4 = [0, 0, 0, 2, 2, 2, 0, 2, 2, 2, 0x68, 0xff, 0xff, 0, 0, 0, 0, 0]
            with open(os.path.join(extract_dir, ctxr_name), "wb") as f:
                ctxr.writeToFile(f)
