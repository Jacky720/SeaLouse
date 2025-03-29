from __future__ import annotations
from io import BufferedReader, BufferedWriter
import struct
from ..kms.kms import KMSVector3


class CMDL:
    header: CMDLHeader
    sections: List[CMDLSection]
    tail: CMDLTail
    
    def __init__(self):
        self.header = CMDLHeader()
        self.sections = []
        self.tail = CMDLTail()
    
    def fromFile(self, file: BufferedReader):
        self.header.fromFile(file)
        
        self.sections = [
            CMDLSection().fromFile(file)
            for _ in range(self.header.numSection)
        ]
        
        file.seek(self.header.tailOffset + 0xC)
        self.tail.fromFile(file)
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        # TODO
        self.header.numSection = len(self.sections)
        # self.header.tailOffset
        for section in self.sections:
            section.dataSize = section.data.size * len(section.data.data)
            
        return


class CMDLHeader:
    magic: bytes
    version: int
    tailOffset: int
    numSection: int
    
    def __init__(self):
        self.magic = b"MODL"
        self.version = 1
        self.tailOffset = 0
        self.numSection = 0
    
    def fromFile(self, file: BufferedReader):
        self.magic = file.read(4)
        assert(self.magic == b"MODL") # Unexpected header magic
        self.version, self.tailOffset = struct.unpack(">II", file.read(8))
        assert(self.version == 1) # Unexpected header version
        self.numSection = struct.unpack("<I", file.read(4))[0]
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(self.magic)
        file.write(struct.pack(">II", self.version, self.tailOffset))
        file.write(struct.pack("<I", self.numSection))


class CMDLSection:
    magic: bytes
    unknown_04: int # No! That is NOT zero!
    unknown_06: int
    dataOffset: int
    dataSize: int
    data: CMDLSectionData
    
    def __init__(self):
        self.magic = "xxxx"
        self.unknown_04 = 0
        self.unknown_06 = 2
        self.dataOffset = 0
        self.dataSize = 0
    
    def fromFile(self, file: BufferedReader):
        self.magic = bytes(reversed(file.read(4)))
        assert(self.magic in { "POS0", "NRM0", "OIDX" } or self.magic[:3] == b"TEX") # Unexpected section magic
        self.unknown_04, self.unknown_06, self.dataOffset, pad \
        = struct.unpack("<HHII", file.read(0xC))
        assert(pad == 0) # Expected zero
        self.dataSize, pad1, pad2, pad3 = struct.unpack("<IIII", file.read(0x10))
        assert(pad1 == 0 and pad2 == 0 and pad3 == 0) # Expected zero
        
        if self.magic == "POS0":
            self.data = CMDLPosData()
        elif self.magic == "NRM0":
            self.data = CMDLNrmData()
        elif self.magic == "OIDX":
            self.data = CMDLOIdxData()
        elif self.magic[:3] == b"TEX":
            self.data = CMDLTexData()
        else:
            assert(False) # How did we get here?
        
        curPos = file.tell()
        file.seek(self.dataOffset + 0xC)
        self.data.fromFile(file, self.dataSize)
        file.seek(curPos)
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(bytes(reversed(self.magic)))
        file.write(struct.pack("<HHIIIIII", self.unknown_04, self.unknown_06, self.dataOffset, 0, \
        self.dataSize, 0, 0, 0))
        
        curPos = file.tell()
        file.seek(self.dataOffset + 0xC)
        self.data.writeToFile(file)
        file.seek(curPos)


class CMDLSectionData:
    data: List[any]
    size: int
    
    def __init__(self):
        self.data = []
    def fromFile(self, file: BufferedReader):
        assert(False) # Attempt to read an abstract class
    def writeToFile(self, file: BufferedWriter):
        assert(False) # Attempt to write an abstract class

class CMDLPosData(CMDLSectionData): # Coordinates
    size = 0x10
    
    def fromFile(self, file: BufferedReader, fullSize: int):
        vertCount = fullSize // size
        self.data = [struct.unpack("<ffff", file.read(0x10)) for _ in range(vertCount)]
        assert(all(x[3] == 1.0 for x in self.data)) # Unexpected "w" (v4) value in vertex position
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        for vert in self.data:
            file.write(struct.pack("<ffff", vert[0], vert[1], vert[2], vert[3]))

class CMDLNrmData(CMDLSectionData): # Normals
    size = 4
    
    def fromFile(self, file: BufferedReader, fullSize: int):
        vertCount = fullSize // size
        for _ in range(vertCount):
            # I would like to express my profound gratitude to... I forget where I found this.
            # Either WoefulWolf's Nier2Blender2Nier, Kerilk's bayonetta_tools, or I wrote it myself based on both
            # 11-bit x, 11-bit y, 10-bit z
            normal = struct.unpack("<I", file.read(4))[0]
            
            normalX = normal & ((1 << 11) - 1)
            normalY = (normal >> 11) & ((1 << 11) - 1)
            normalZ = (normal >> 22)
            # sign bits
            if normalX & (1 << 10):
                normalX &= ~(1 << 10)
                normalX -= 1 << 10
            if normalY & (1 << 10):
                normalY &= ~(1 << 10)
                normalY -= 1 << 10
            if normalZ & (1 << 9):
                normalZ &= ~(1 << 9)
                normalZ -= 1 << 9
            # normalize
            normalX /= (1<<10)-1
            normalY /= (1<<10)-1
            normalZ /= (1<<9)-1
            
            self.data.append((normalX, normalY, normalZ))
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        for vert in self.data:
            # I know where this code came from, it was ChatGPT when told to reverse that other code
            nx = int(round(vert[0] * float((1<<10)-1)))
            ny = int(round(vert[1] * float((1<<10)-1)))
            nz = int(round(vert[2] * float((1<<9 )-1)))
            if nx < 0:
                nx += (1 << 10)
                nx |= 1 << 10
            if ny < 0:
                ny += (1 << 10)
                ny |= 1 << 10
            if nz < 0:
                nz += (1 << 9)
                nz |= 1 << 9
            normal = nx | (ny << 11) | (nz << 22)
            
            file.write(struct.pack("<I", normal))

class CMDLTexData(CMDLSectionData): # UV maps
    size = 4
    
    def fromFile(self, file: BufferedReader, fullSize: int):
        vertCount = fullSize // size
        # Everybody loves the half-precision float format (5 bit exponent, 10 bit mantissa)
        self.data = [struct.unpack("<ee", file.read(4)) for _ in range(vertCount)]
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        for vert in self.data:
            file.write(struct.pack("<ee", vert[0], vert[1]))

class CMDLOIdxData(CMDLSectionData): # Point back to KMS indices
    size = 4
    
    def fromFile(self, file: BufferedReader, fullSize: int):
        vertCount = fullSize // size
        self.data = [struct.unpack("<I", file.read(4))[0] for _ in range(vertCount)]
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        for vert in self.data:
            file.write(struct.pack("<I", vert))


class CMDLTail:
    numFaces: int
    faces: List[List[int]]
    numMeshes: int
    meshes: List[CMDLMesh]
    
    def __init__(self):
        self.numFaces = 0
        self.faces = []
        self.numMeshes = 0
        self.meshes = []
    
    def fromFile(self, file: BufferedReader):
        numFaceIndexes = struct.unpack(">I", file.read(4))[0]
        assert(numFaceIndexes % 3 == 0) # Unexpected face index count
        self.numFaces = numFaceIndexes // 3
        self.faces = [struct.unpack(">III", file.read(0xC)) for _ in range(self.numFaces)]
        pad, self.numMeshes = struct.unpack(">II", file.read(8))
        assert(pad == 0) # Expected zero
        self.meshes = [
            CMDLMesh().fromFile(file)
            for _ in range(self.numMeshes)
        ]
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack(">I", self.numFaces * 3))
        for face in self.faces:
            file.write(struct.pack(">III", face[0], face[1], face[2]))
        
        file.write(struct.pack(">II", 0, self.numMeshes))
        for mesh in self.meshes:
            mesh.writeToFile(file)
        
class CMDLMesh:
    minPos: KMSVector3
    maxPos: KMSVector3
    unknown_18: int # two bytes, -1
    unknown_1C: int # one byte
    startVertex: int
    vertexCount: int
    startFace: int
    faceCount: int # x3
    unknown_2D: int # four bytes
    unknown_2E: bytes # 8 bytes, all 0x80
    unknown_36: int # one byte
    meshIndex: int
    subMeshIndex: int
    
    def __init__(self):
        self.minPos = KMSVector3()
        self.minPos.x = 0.0
        self.minPos.y = 0.0
        self.minPos.z = 0.0
        self.maxPos = KMSVector3()
        self.maxPos.x = 0.0
        self.maxPos.y = 0.0
        self.maxPos.z = 0.0
        self.unknown_18 = -1
        self.unknown_1C = 0
        self.startVertex = 0
        self.vertexCount = 0
        self.startFace = 0
        self.faceCount = 0
        self.unknown_2D = 0
        self.unknown_2E = b"\x80\x80\x80\x80\x80\x80\x80\x80"
        self.unknown_36 = 0
        self.meshIndex = 0
        self.subMeshIndex = 0
    
    def fromFile(self, file: BufferedReader):
        self.minPos.fromFile(file, True)
        self.maxPos.fromFile(file, True)
        self.unknown_18, self.unknown_1C, \
        self.startVertex, self.vertexCount, self.startFace, self.faceCount, \
        self.unknown_2D = struct.unpack(">hBIIIII", file.read(23)) # this BS doesn't deserve hexadecimal
        assert(self.unknown_18 == -1) # Expected -1
        assert(self.unknown_1C == 0) # Expected 0
        assert(self.unknown_2D == 0) # Expected 0
        self.unknown_2E = file.read(8)
        assert(self.unknown_2E == b"\x80\x80\x80\x80\x80\x80\x80\x80") # Expected... whatever this is
        self.unknown_36, self.meshIndex, self.subMeshIndex \
        = struct.unpack(">III", file.read(0xC))
        assert(self.unknown_36 == 0) # Expected 0
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        self.minPos.writeToFile(file, True)
        self.maxPos.writeToFile(file, True)
        file.write(struct.pack(">hBIIIII", self.unknown_18, self.unknown_1C, \
        self.startVertex, self.vertexCount, self.startFace, self.faceCount, \
        self.unknown_2D))
        file.write(self.unknown_2E)
        file.write(struct.pack(">III", self.unknown_36, self.meshIndex, self.subMeshIndex))
