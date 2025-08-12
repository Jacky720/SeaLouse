from __future__ import annotations
from io import BufferedReader, BufferedWriter
import struct

def readPad(padArray: List[int], file: BufferedReader):
    for pad in range(len(padArray)):
        padArray[pad] = struct.unpack("<I", file.read(4))
        if padArray[pad] != 0:
            print("Unexpected non-zero pad detected.")

def writePad(padArray: List[int], file: BufferedWriter):
    for pad in padArray:
        file.write(struct.pack("<I", pad))
        if pad != 0:
            print("Unexpected non-zero pad written.")

def padOffset(offset: int, pad_amount: int = 0x10):
    if offset % pad_amount == 0:
        return offset
    return offset - (offset % pad_amount) + pad_amount

class EVM:
    header: EVMHeader
    meshes: List[EVMMesh]
    bones: List[EVMBone]
    
    def __init__(self):
        self.header = EVMHeader()
        self.meshes = []
        self.bones = []
    
    def fromFile(self, file: BufferedReader):
        self.header = EVMHeader().fromFile(file)
        
        self.bones = [
            EVMBone().fromFile(file)
            for _ in range(self.header.numBones)
        ]
        
        for bone in self.bones:
            bone.parent = self.bones[bone.parentInd] if bone.parentInd > -1 else None
        
        file.seek(self.header.meshOffset)
        
        self.meshes = [
            EVMMesh().fromFile(file)
            for _ in range(self.header.numMeshes)
        ]
        
        return self
    
    def writeToFile(self, file: BufferedWriter, vanilla_mode: bool = False):
        self.header.numMeshes = len(self.meshes)
        self.header.numBones = len(self.bones)
        self.header.numUnknown = len(self.bones)
        self.header.meshOffset = 0x40 + 0x40 * len(self.bones)
        i = 0
        for mesh in self.meshes:
            print("Mesh %d" % i)
            i += 1
            vertCount = len(mesh.vertices)
            mesh.numVertex = vertCount
            # Sanity checks
            if len(mesh.normals) != vertCount:
                print("ERROR: Normal count does not match vertex count")
                return
            if mesh.uvs != None and len(mesh.uvs) != vertCount:
                print("Error: UV 1 count does not match vertex count")
                return
            if mesh.uvs2 != None and len(mesh.uvs2) != vertCount:
                print("Error: UV 2 count does not match vertex count")
                return
            if mesh.uvs3 != None and len(mesh.uvs3) != vertCount:
                print("Error: UV 3 count does not match vertex count")
                return
            if mesh.weights != None and len(mesh.weights) != vertCount:
                print("Error: Weight count does not match vertex count")
                return
        
        firstExDataOffset = self.header.meshOffset + 0x70 * self.header.numMeshes
        
        
        file.seek(0)
        
        self.header.writeToFile(file)
        
        for bone in self.bones:
            bone.writeToFile(file)
        
        curExDataOffset = firstExDataOffset
        for mesh in self.meshes:
            mesh.vertexOffset = curExDataOffset
            curExDataOffset += 0x8 * mesh.numVertex
            curExDataOffset = padOffset(curExDataOffset)
        for mesh in self.meshes:
            mesh.normalOffset = curExDataOffset
            curExDataOffset += 0x8 * mesh.numVertex
            curExDataOffset = padOffset(curExDataOffset)

        for mesh in self.meshes:
            if mesh.uvs != None and any((x.u, x.v) != (0, 0) for x in mesh.uvs):
                mesh.uvOffset = curExDataOffset
                curExDataOffset += 0x8 * mesh.numVertex
            else:
                mesh.uvOffset = 0
                mesh.uvs = None
            curExDataOffset = padOffset(curExDataOffset)
        for mesh in self.meshes:
            if mesh.uvs2 != None and any((x.u, x.v) != (0, 0) for x in mesh.uvs2):
                mesh.uv2Offset = curExDataOffset
                curExDataOffset += 0x8 * mesh.numVertex
            else:
                mesh.uv2Offset = 0
                mesh.uvs2 = None
            curExDataOffset = padOffset(curExDataOffset)
        for mesh in self.meshes:
            if mesh.uvs3 != None and any((x.u, x.v) != (0, 0) for x in mesh.uvs3):
                mesh.uv3Offset = curExDataOffset
                curExDataOffset += 0x8 * mesh.numVertex
            else:
                mesh.uv3Offset = 0
                mesh.uvs3 = None
            curExDataOffset = padOffset(curExDataOffset)
        for mesh in self.meshes:
            if mesh.weights != None:
                mesh.weightOffset = curExDataOffset
                curExDataOffset += 0x8 * mesh.numVertex
            else:
                mesh.weightOffset = 0
            curExDataOffset = padOffset(curExDataOffset)
                
        for mesh in self.meshes:
            mesh.writeToFile(file)
            returnPos = file.tell()
        
            file.seek(mesh.vertexOffset)
            for vert in mesh.vertices:
                vert.writeToFile(file)
            file.seek(mesh.normalOffset)
            for normal in mesh.normals:
                normal.writeToFile(file)
            file.seek(mesh.uvOffset)
            if mesh.uvs != None:
                for uv in mesh.uvs:
                    uv.writeToFile(file)
            file.seek(mesh.uv2Offset)
            if mesh.uvs2 != None:
                for uv in mesh.uvs2:
                    uv.writeToFile(file)
            file.seek(mesh.uv3Offset)
            if mesh.uvs3 != None:
                for uv in mesh.uvs3:
                    uv.writeToFile(file)
            file.seek(mesh.weightOffset)
            if mesh.weights != None:
                for weight in mesh.weights:
                    weight.writeToFile(file)
            
            file.seek(returnPos)


class EVMHeader:
    numUnknown: int
    numBones: int
    minPos: EVMVector3
    maxPos: EVMVector3
    strcode: int
    pad: int
    flag: int
    numMeshes: int
    meshOffset: int
    pad2: List[int] # 3 items
    
    def __init__(self):
        self.numUnknown = 0
        self.numBones = 0
        self.minPos = EVMVector3()
        self.maxPos = EVMVector3()
        self.strcode = 0
        self.pad = 0
        self.flag = 0
        self.numMeshes = 0
        self.pad2 = [0, 0, 0]
    
    def fromFile(self, file: BufferedReader):
        self.numUnknown, self.numBones = struct.unpack("<II", file.read(8))
        self.minPos.fromFile(file)
        self.maxPos.fromFile(file)
        self.strcode, self.pad, self.flag, self.numMeshes, \
        self.meshOffset = struct.unpack("<IIIiI", file.read(0x14))
        readPad(self.pad2, file)
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<II", self.numUnknown, self.numBones))
        self.minPos.writeToFile(file)
        self.maxPos.writeToFile(file)
        file.write(struct.pack("<IIIiI", self.strcode, self.pad, self.flag, self.numMeshes, \
        self.meshOffset))
        writePad(self.pad2, file)


class EVMBone:
    pad: int
    parentInd: int
    relativePos: EVMVector3
    worldPos: EVMVector3
    minPos: EVMVector4
    maxPos: EVMVector4
    
    parent: EVMBone
    
    def __init__(self):
        self.pad = 0
        self.parentInd = -1
        self.relativePos = EVMVector3()
        self.worldPos = EVMVector3()
        self.minPos = EVMVector4()
        self.maxPos = EVMVector4()
        self.parent = None
    
    def fromFile(self, file: BufferedReader):
        self.pad, self.parentInd = struct.unpack("<Ii", file.read(8))
        self.relativePos.fromFile(file)
        self.worldPos.fromFile(file)
        self.minPos.fromFile(file)
        self.maxPos.fromFile(file)
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<Ii", self.pad, self.parentInd))
        self.relativePos.writeToFile(file)
        self.worldPos.writeToFile(file)
        self.minPos.writeToFile(file)
        self.maxPos.writeToFile(file)


class EVMVector3:
    x: float
    y: float
    z: float
    
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
    
    def fromFile(self, file: BufferedReader, bigEndian: bool = False):
        formatstr = ">fff" if bigEndian else "<fff"
        self.x, self.y, self.z = struct.unpack(formatstr, file.read(0xC))
        return self
    
    def writeToFile(self, file: BufferedWriter, bigEndian: bool = False):
        formatstr = ">fff" if bigEndian else "<fff"
        file.write(struct.pack(formatstr, self.x, self.y, self.z))
    
    """Helper methods"""
    def xyz(self):
        return [self.x, self.y, self.z]
    
    def __add__(self, other):
        if type(other) is not EVMVector3:
            raise TypeError("Can only add EVMVector3 to another EVMVector3")
        return EVMVector3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other):
        if type(other) is not EVMVector3:
            raise TypeError("Can only subtract EVMVector3 from another EVMVector3")
        return EVMVector3(self.x - other.x, self.y - other.y, self.z - other.z)

class EVMVector4:
    x: float
    y: float
    z: float
    w: float
    
    def __init__(self, x=0.0, y=0.0, z=0.0, w=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.w = float(w)
    
    def fromFile(self, file: BufferedReader, bigEndian: bool = False):
        formatstr = ">ffff" if bigEndian else "<ffff"
        self.x, self.y, self.z, self.w = struct.unpack(formatstr, file.read(0x10))
        return self
    
    def writeToFile(self, file: BufferedWriter, bigEndian: bool = False):
        formatstr = ">ffff" if bigEndian else "<ffff"
        file.write(struct.pack(formatstr, self.x, self.y, self.z, self.w))
    
    """Helper methods"""
    def xyzw(self):
        return [self.x, self.y, self.z, self.w]
    
    def __add__(self, other):
        if type(other) is not EVMVector4:
            raise TypeError("Can only add EVMVector4 to another EVMVector4")
        return EVMVector4(self.x + other.x, self.y + other.y, self.z + other.z, self.w + other.w)
    
    def __sub__(self, other):
        if type(other) is not EVMVector4:
            raise TypeError("Can only subtract EVMVector4 from another EVMVector4")
        return EVMVector4(self.x - other.x, self.y - other.y, self.z - other.z, self.w - other.w)


class EVMMesh:
    flag: int
    pad: int
    colorMap: int
    pad2: int
    specularMap: int
    pad3: int
    environmentMap: int
    pad4: int
    numVertex: int
    numSkin: int
    skinningTable: List[int] # always 8 items despite allowing fewer
    vertexOffset: int
    pad5: int
    normalOffset: int
    pad6: int
    uvOffset: int
    pad7: int
    uv2Offset: int
    pad8: int
    uv3Offset: int
    pad9: int
    weightOffset: int
    pad10: List[int] # 5 items
    
    vertices: List[EVMVertex]
    normals: List[EVMNormal]
    uvs: List[EVMUv] | None
    uvs2: List[EVMUv] | None
    uvs3: List[EVMUv] | None
    weights: List[EVMWeights] | None
    
    def __init__(self):
        self.flag = 0
        self.pad = 0
        self.colorMap = 0
        self.pad2 = 0
        self.specularMap = 0
        self.pad3 = 0
        self.environmentMap = 0
        self.pad4 = 0
        self.numVertex = 0
        self.numSkin = 0
        self.skinningTable = [255] * 8
        self.vertexOffset = 0
        self.pad5 = 0
        self.normalOffset = 0
        self.pad6 = 0
        self.uvOffset = 0
        self.pad7 = 0
        self.uv2Offset = 0
        self.pad8 = 0
        self.uv3Offset = 0
        self.pad9 = 0
        self.weightOffset = 0
        self.pad10 = [0] * 5
        
        self.vertices = []
        self.normals = []
        self.uvs = None
        self.uvs2 = None
        self.uvs3 = None
        self.weights = None
    
    def fromFile(self, file: BufferedReader):
        self.flag, self.pad, self.colorMap, self.pad2, \
        self.specularMap, self.pad3, self.environmentMap, self.pad4, \
        self.numVertex, self.numSkin = struct.unpack("<10I", file.read(0x28))
        self.skinningTable = list(struct.unpack("<8B", file.read(8)))
        self.vertexOffset, self.pad5, self.normalOffset, self.pad6, \
        self.uvOffset, self.pad7, self.uv2Offset, self.pad8, \
        self.uv3Offset, self.pad9, self.weightOffset \
        = struct.unpack("<11I", file.read(0x2C))
        readPad(self.pad10, file)
        
        curPos = file.tell()
        
        #print(self.vertexOffset, self.numVertex)
        file.seek(self.vertexOffset)
        self.vertices = [
            EVMVertex().fromFile(file)
            for _ in range(self.numVertex)
        ]
        
        file.seek(self.normalOffset)
        self.normals = [
            EVMNormal().fromFile(file)
            for _ in range(self.numVertex)
        ]
        
        if self.uvOffset > 0:
            file.seek(self.uvOffset)
            self.uvs = [
                EVMUv().fromFile(file)
                for _ in range(self.numVertex)
            ]
        else:
            self.uvs = None
        
        if self.uv2Offset > 0:
            file.seek(self.uv2Offset)
            self.uvs2 = [
                EVMUv().fromFile(file)
                for _ in range(self.numVertex)
            ]
        else:
            self.uvs2 = None
        
        if self.uv3Offset > 0:
            file.seek(self.uv3Offset)
            self.uvs3 = [
                EVMUv().fromFile(file)
                for _ in range(self.numVertex)
            ]
        else:
            self.uvs3 = None
        
        if self.weightOffset > 0:
            file.seek(self.weightOffset)
            self.weights = [
                EVMWeights().fromFile(file)
                for _ in range(self.numVertex)
            ]
        else:
            self.weights = None
        
        file.seek(curPos)
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<10I", self.flag, self.pad, self.colorMap, self.pad2, \
        self.specularMap, self.pad3, self.environmentMap, self.pad4, \
        self.numVertex, self.numSkin))
        for boneIndex in self.skinningTable:
            file.write(struct.pack("<B", boneIndex))
        file.write(struct.pack("<11I", self.vertexOffset, self.pad5, self.normalOffset, self.pad6, \
        self.uvOffset, self.pad7, self.uv2Offset, self.pad8, \
        self.uv3Offset, self.pad9, self.weightOffset))
        writePad(self.pad10, file)
        return


class EVMVertex:
    x: int
    y: int
    z: int
    flags: int
    isFace: bool
    
    def __init__(self, x=0, y=0, z=0, isFace=False):
        self.x = int(x)
        self.y = int(y)
        self.z = int(z)
        self.flags = 0x8fff
        self.isFace = isFace
    
    def fromFile(self, file: BufferedReader):
        self.x, self.y, self.z, self.flags = struct.unpack("<hhhH", file.read(0x8))
        
        self.isFace = not (self.flags & 0x8000)
        return self
    
    def writeToFile(self, file: BufferedWriter):
        if self.isFace:
            self.flags &= ~0x8000
        else:
            self.flags |= 0x8000
        file.write(struct.pack("<hhhH", self.x, self.y, self.z, self.flags))
    
    """Helper methods"""
    def xyz(self):
        return [self.x, self.y, self.z]

class EVMNormal:
    x: int
    y: int
    z: int
    pad: int
    
    isFace: bool
    
    def __init__(self, x=0, y=0, z=0):
        self.x = int(x)
        self.y = int(y)
        self.z = int(z)
        self.pad = 0
    
    def fromFile(self, file: BufferedReader):
        self.x, self.y, self.z, self.pad = struct.unpack("<hhhh", file.read(0x8))
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        
        file.write(struct.pack("<hhhh", self.x, self.y, self.z, self.pad))

class EVMUv:
    u: int
    v: int
    unknown: int
    
    def __init__(self, u=0, v=0):
        self.u = int(u)
        self.v = int(v)
        self.unknown = 0x1000
    
    def fromFile(self, file: BufferedReader):
        self.u, self.v, self.unknown = struct.unpack("<hhI", file.read(0x8))
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<hhI", self.u, self.v, self.unknown))

class EVMWeights:
    weights: List[int] # read 4, handle up to numWeights
    indices: List[int] # read 4, handle up to numWeights
    
    def __init__(self, weights=None, indices=None):
        if weights is None:
            weights = []
        if indices is None:
            indices = []
        self.weights = weights
        self.indices = indices
        while len(self.weights) < 4:
            self.weights.append(0)
            self.indices.append(0)
    
    def fromFile(self, file: BufferedReader):
        weights = list(struct.unpack("<8B", file.read(8)))
        self.indices = weights[4:]
        self.weights = weights[:4]
        return self
    
    def writeToFile(self, file: BufferedWriter):
        for weight in self.weights:
            file.write(struct.pack("<B", weight))
        for index in self.indices:
            file.write(struct.pack("<B", index))
