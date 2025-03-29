from __future__ import annotations
from io import BufferedReader, BufferedWriter
import struct


class KMS:
    header: KMSHeader
    meshes: List[KMSMesh]
    
    def fromFile(self, file: BufferedReader):
        self.header = KMSHeader().fromFile(file)
        
        self.meshes = [
            KMSMesh().fromFile(file)
            for _ in range(self.header.numMesh)
        ]
        
        for mesh in self.meshes:
            mesh.parent = self.meshes[mesh.parentInd] if mesh.parentInd > -1 else None
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        self.header.numMesh = len(self.meshes)
        for mesh in self.meshes:
            mesh.numVertexGroup = len(mesh.vertexGroups)
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
                vertexGroup.normalOffset = curExDataOffset
                curExDataOffset += 0x8 * vertexGroup.numVertex
                if vertexGroup.uvs != None:
                    vertexGroup.uvOffset = curExDataOffset
                    curExDataOffset += 0x4 * vertexGroup.numVertex
                else:
                    vertexGroup.uvOffset = 0
                
                if vertexGroup.uvs2 != None:
                    vertexGroup.uv2Offset = curExDataOffset
                    curExDataOffset += 0x4 * vertexGroup.numVertex
                else:
                    vertexGroup.uv2Offset = 0
                
                if vertexGroup.uvs3 != None:
                    vertexGroup.uv3Offset = curExDataOffset
                    curExDataOffset += 0x4 * vertexGroup.numVertex
                else:
                    vertexGroup.uv3Offset = 0
                
                vertexGroup.writeToFile(file)
        
        for mesh in self.meshes:
            for vertexGroup in mesh.vertexGroups:
                for vert in vertexGroup.vertices:
                    vert.writeToFile(file)
                for normal in vertexGroup.normals:
                    normal.writeToFile(file)
                if vertexGroup.uvs != None:
                    for uv in vertexGroup.uvs:
                        uv.writeToFile(file)
                if vertexGroup.uvs2 != None:
                    for uv in vertexGroup.uvs2:
                        uv.writeToFile(file)
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
    
    def fromFile(self, file: BufferedReader):
        self.kmsType, self.numMesh, self.numBones, self.pad, \
        self.strcode, self.pad2, self.pad3 \
        = struct.unpack("<IIiIIII", file.read(0x1C))
        self.minPos = KMSVector3().fromFile(file)
        self.maxPos = KMSVector3().fromFile(file)
        self.pos = KMSVector3().fromFile(file)
        
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
    
    def fromFile(self, file: BufferedReader):
        self.flag, self.numVertexGroup = struct.unpack("<II", file.read(0x8))
        self.minPos = KMSVector3().fromFile(file)
        self.maxPos = KMSVector3().fromFile(file)
        self.pos = KMSVector3().fromFile(file)
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
        print("VertexGroup write TODO")
        return


class KMSVertex:
    x: int
    y: int
    z: int
    weight: int
    
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
    
    def fromFile(self, file: BufferedReader):
        self.u, self.v = struct.unpack("<hh", file.read(0x4))
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<hh", self.u, self.v))
