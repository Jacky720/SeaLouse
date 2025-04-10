from __future__ import annotations
from io import BufferedReader, BufferedWriter
import struct


class KMS:
    header: KMSHeader
    meshes: List[KMSMesh]
    
    def __init__(self):
        self.header = KMSHeader()
        self.meshes = []
    
    def fromFile(self, file: BufferedReader):
        self.header = KMSHeader().fromFile(file)
        
        self.meshes = [
            KMSMesh().fromFile(file)
            for _ in range(self.header.numMesh)
        ]
        
        for mesh in self.meshes:
            mesh.parent = self.meshes[mesh.parentInd] if mesh.parentInd > -1 else None
        
        return self
    
    def writeToFile(self, file: BufferedWriter, vanilla_mode: bool = False):
        self.header.numMesh = len(self.meshes)
        if not vanilla_mode:
            self.header.numBones = len(self.meshes)
        i = 0
        for mesh in self.meshes:
            mesh.numVertexGroup = len(mesh.vertexGroups)
            print("Mesh %d: %d vertex groups" % (i, mesh.numVertexGroup))
            i += 1
            for vertexGroup in mesh.vertexGroups:
                vertCount = len(vertexGroup.vertices)
                vertexGroup.numVertex = vertCount
                # Sanity checks
                if len(vertexGroup.normals) != vertCount:
                    print("ERROR: Normal count does not match vertex count")
                    return
                if vertexGroup.uvs != None and len(vertexGroup.uvs) != vertCount:
                    print("Error: UV 1 count does not match vertex count")
                    return
                if vertexGroup.uvs2 != None and len(vertexGroup.uvs2) != vertCount:
                    print("Error: UV 2 count does not match vertex count")
                    return
                if vertexGroup.uvs3 != None and len(vertexGroup.uvs3) != vertCount:
                    print("Error: UV 3 count does not match vertex count")
                    return
        
        firstMeshOffset = 0x40
        firstVertexGroupOffset = firstMeshOffset + 0x50 * self.header.numMesh
        firstExDataOffset = firstVertexGroupOffset + 0x60 * sum(mesh.numVertexGroup for mesh in self.meshes)
        
        
        file.seek(0)
        
        self.header.writeToFile(file)
        
        curVertexGroupOffset = firstVertexGroupOffset
        for mesh in self.meshes:
            mesh.vertexGroupOffset = curVertexGroupOffset
            curVertexGroupOffset += 0x60 * mesh.numVertexGroup
            mesh.writeToFile(file)
        
        curExDataOffset = firstExDataOffset
        for mesh in self.meshes:
            for vertexGroup in mesh.vertexGroups:
                vertexGroup.vertexOffset = curExDataOffset
                curExDataOffset += 0x8 * vertexGroup.numVertex
                if curExDataOffset % 0x10 > 0:
                    curExDataOffset = (curExDataOffset + 0xf) & ~0xf # fun rounding-up trick
        for mesh in self.meshes:
            for vertexGroup in mesh.vertexGroups:
                vertexGroup.normalOffset = curExDataOffset
                curExDataOffset += 0x8 * vertexGroup.numVertex
                if curExDataOffset % 0x10 > 0:
                    curExDataOffset = (curExDataOffset + 0xf) & ~0xf

        for mesh in self.meshes:
            for vertexGroup in mesh.vertexGroups:
                if vertexGroup.uvs != None:
                    vertexGroup.uvOffset = curExDataOffset
                    curExDataOffset += 0x4 * vertexGroup.numVertex
                else:
                    vertexGroup.uvOffset = 0
                if curExDataOffset % 0x10 > 0:
                    curExDataOffset = (curExDataOffset + 0xf) & ~0xf
            for vertexGroup in mesh.vertexGroups:
                if vertexGroup.uvs2 != None:
                    vertexGroup.uv2Offset = curExDataOffset
                    curExDataOffset += 0x4 * vertexGroup.numVertex
                else:
                    vertexGroup.uv2Offset = 0
                if curExDataOffset % 0x10 > 0:
                    curExDataOffset = (curExDataOffset + 0xf) & ~0xf
            for vertexGroup in mesh.vertexGroups:
                if vertexGroup.uvs3 != None:
                    vertexGroup.uv3Offset = curExDataOffset
                    curExDataOffset += 0x4 * vertexGroup.numVertex
                else:
                    vertexGroup.uv3Offset = 0
                if curExDataOffset % 0x10 > 0:
                    curExDataOffset = (curExDataOffset + 0xf) & ~0xf
                
        for mesh in self.meshes:
            for vertexGroup in mesh.vertexGroups:
                vertexGroup.writeToFile(file)
        
        for mesh in self.meshes:
            for vertexGroup in mesh.vertexGroups:
                file.seek(vertexGroup.vertexOffset)
                for vert in vertexGroup.vertices:
                    vert.writeToFile(file)
        for mesh in self.meshes:
            for vertexGroup in mesh.vertexGroups:
                file.seek(vertexGroup.normalOffset)
                for normal in vertexGroup.normals:
                    normal.writeToFile(file)
        for mesh in self.meshes:
            for vertexGroup in mesh.vertexGroups:
                file.seek(vertexGroup.uvOffset)
                if vertexGroup.uvs != None:
                    for uv in vertexGroup.uvs:
                        uv.writeToFile(file)
            for vertexGroup in mesh.vertexGroups:
                file.seek(vertexGroup.uv2Offset)
                if vertexGroup.uvs2 != None:
                    for uv in vertexGroup.uvs2:
                        uv.writeToFile(file)
            for vertexGroup in mesh.vertexGroups:
                file.seek(vertexGroup.uv3Offset)
                if vertexGroup.uvs3 != None:
                    for uv in vertexGroup.uvs3:
                        uv.writeToFile(file)


class KMSHeader:
    kmsType: int
    numMesh: int
    numBones: int
    pad: int
    strcode: int
    pad2: int
    pad3: int
    minPos: KMSVector3
    maxPos: KMSVector3
    pos: KMSVector3
    
    def __init__(self):
        self.kmsType = 0
        self.numMesh = 0
        self.numBones = 0
        self.pad = 0
        self.strcode = 0
        self.pad2 = 0
        self.pad3 = 0
        self.minPos = KMSVector3()
        self.maxPos = KMSVector3()
        self.pos = KMSVector3()
    
    def fromFile(self, file: BufferedReader):
        self.kmsType, self.numMesh, self.numBones, self.pad, \
        self.strcode, self.pad2, self.pad3 \
        = struct.unpack("<IIiIIII", file.read(0x1C))
        self.minPos.fromFile(file)
        self.maxPos.fromFile(file)
        self.pos.fromFile(file)
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<IIiIIII", \
        self.kmsType, self.numMesh, self.numBones, self.pad, \
        self.strcode, self.pad2, self.pad3))
        self.minPos.writeToFile(file)
        self.maxPos.writeToFile(file)
        self.pos.writeToFile(file)


class KMSVector3:
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


class KMSMesh:
    flag: int
    numVertexGroup: int
    minPos: KMSVector3
    maxPos: KMSVector3
    pos: KMSVector3
    parentInd: int
    vertexGroupOffset: int
    pad: List[int] # 7 items
    
    vertexGroups: List[KMSVertexGroup]
    parent: KMSMesh | None
    
    def __init__(self):
        self.flag = 0
        self.numVertexGroup = 0
        self.minPos = KMSVector3()
        self.maxPos = KMSVector3()
        self.pos = KMSVector3()
        self.parentInd = -1
        self.vertexGroupOffset = 0
        self.pad = [0] * 7
        self.vertexGroups = []
        self.parent = None
    
    def fromFile(self, file: BufferedReader):
        self.flag, self.numVertexGroup = struct.unpack("<II", file.read(0x8))
        self.minPos.fromFile(file)
        self.maxPos.fromFile(file)
        self.pos.fromFile(file)
        self.parentInd, self.vertexGroupOffset = struct.unpack("<iI", file.read(0x8))
        self.pad = list(struct.unpack("<7I", file.read(0x1C)))
        
        curPos = file.tell()
        
        file.seek(self.vertexGroupOffset)
        
        self.vertexGroups = [
            KMSVertexGroup().fromFile(file)
            for _ in range(self.numVertexGroup)
        ]
        
        file.seek(curPos)
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<II", \
        self.flag, self.numVertexGroup))
        self.minPos.writeToFile(file)
        self.maxPos.writeToFile(file)
        self.pos.writeToFile(file)
        file.write(struct.pack("<iI", \
        self.parentInd, self.vertexGroupOffset))
        for i in range(7):
            file.write(struct.pack("<I", self.pad[i]))


class KMSVertexGroup:
    flag: int
    numVertex: int
    colorMap: int
    pad: int
    specularMap: int
    pad2: int
    environmentMap: int
    pad3: int
    vertexOffset: int
    pad4: int
    normalOffset: int
    pad5: int
    uvOffset: int
    pad6: int
    uv2Offset: int
    pad7: int
    uv3Offset: int
    pad8: List[int] # 7 items
    
    vertices: List[KMSVertex]
    normals: List[KMSNormal]
    uvs: List[KMSUv] | None
    uvs2: List[KMSUv] | None
    uvs3: List[KMSUv] | None
    
    def __init__(self):
        self.flag = 0
        self.numVertex = 0
        self.colorMap = 0
        self.pad = 0
        self.specularMap = 0
        self.pad2 = 0
        self.environmentMap = 0
        self.pad3 = 0
        self.vertexOffset = 0
        self.pad4 = 0
        self.normalOffset = 0
        self.pad5 = 0
        self.uvOffset = 0
        self.pad6 = 0
        self.uv2Offset = 0
        self.pad7 = 0
        self.uv3Offset = 0
        self.pad8 = [0] * 7
        
        self.vertices = []
        self.normals = []
        self.uvs = None
        self.uvs2 = None
        self.uvs3 = None
    
    def fromFile(self, file: BufferedReader):
        self.flag, self.numVertex, self.colorMap, self.pad, \
        self.specularMap, self.pad2, self.environmentMap, self.pad3, \
        self.vertexOffset, self.pad4, self.normalOffset, self.pad5, \
        self.uvOffset, self.pad6, self.uv2Offset, self.pad7, \
        self.uv3Offset = struct.unpack("<17I", file.read(0x44))
        self.pad8 = list(struct.unpack("<7I", file.read(0x1C)))
        
        curPos = file.tell()
        
        file.seek(self.vertexOffset)
        self.vertices = [
            KMSVertex().fromFile(file)
            for _ in range(self.numVertex)
        ]
        
        file.seek(self.normalOffset)
        self.normals = [
            KMSNormal().fromFile(file)
            for _ in range(self.numVertex)
        ]
        
        if self.uvOffset > 0:
            file.seek(self.uvOffset)
            self.uvs = [
                KMSUv().fromFile(file)
                for _ in range(self.numVertex)
            ]
        else:
            self.uvs = None
        
        if self.uv2Offset > 0:
            file.seek(self.uv2Offset)
            self.uvs2 = [
                KMSUv().fromFile(file)
                for _ in range(self.numVertex)
            ]
        else:
            self.uvs2 = None
        
        if self.uv3Offset > 0:
            file.seek(self.uv3Offset)
            self.uvs3 = [
                KMSUv().fromFile(file)
                for _ in range(self.numVertex)
            ]
        else:
            self.uvs3 = None
        
        file.seek(curPos)
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<17I", self.flag, self.numVertex, self.colorMap, self.pad, \
        self.specularMap, self.pad2, self.environmentMap, self.pad3, \
        self.vertexOffset, self.pad4, self.normalOffset, self.pad5, \
        self.uvOffset, self.pad6, self.uv2Offset, self.pad7, \
        self.uv3Offset))
        file.write(struct.pack("<7I", 0, 0, 0, 0, 0, 0, 0))
        return


class KMSVertex:
    x: int
    y: int
    z: int
    weight: int
    
    def __init__(self, x=0, y=0, z=0, weight=4096):
        self.x = int(x)
        self.y = int(y)
        self.z = int(z)
        self.weight = int(weight)
    
    def fromFile(self, file: BufferedReader):
        self.x, self.y, self.z, self.weight = struct.unpack("<hhhh", file.read(0x8))
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<hhhh", self.x, self.y, self.z, self.weight))


class KMSNormal:
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


class KMSUv:
    u: int
    v: int
    
    def __init__(self, u=0, v=0):
        self.u = int(u)
        self.v = int(v)
    
    def fromFile(self, file: BufferedReader):
        self.u, self.v = struct.unpack("<hh", file.read(0x4))
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<hh", self.u, self.v))
