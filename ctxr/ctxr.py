from __future__ import annotations
from io import BufferedReader, BufferedWriter
import struct
from os import path


class CTXR:
    header: CTXRHeader
    chunks: list[CTXRChunk]
    
    def __init__(self):
        self.header = CTXRHeader()
        self.chunks = []
    
    def fromFile(self, file: BufferedReader):
        self.header.fromFile(file)
        
        self.chunks = [
            CTXRChunk().fromFile(file)
            for _ in range(self.header.numMipmaps)
        ]
        
        return self
    
    def convertDDS(self) -> DDS:
        dds = DDS()
        dds.header.flags = 0x2100f
        dds.header.width = self.header.width
        dds.header.height = self.header.height
        dds.header.pitch = 0
        dds.header.numMipmaps = self.header.numMipmaps
        dds.header.pixelFormat.flags = 0x41
        dds.header.caps[0] = 0x1000
        if self.header.numMipmaps > 0:
            dds.header.caps[0] |= 0x400008
        for chunk in self.chunks:
            dds.data += chunk.data
        return dds
    
    def writeToFile(self, file: BufferedWriter):
        self.header.writeToFile(file)
        for chunk in self.chunks:
            chunk.writeToFile(file)

class CTXRHeader:
    magic: bytes  # "TXTR"
    version: int  # 7
    width: int
    height: int
    depth: int
    unknown1: int
    unknown2: int
    unknown3: int  # 0x100
    unknown4: list[int]  # 18 bytes
    numMipmaps: int
    padByte: int
    padding: list[int]  # 22 int32s
    
    def __init__(self):
        self.magic = b"TXTR"
        self.version = 7
        self.width = 0
        self.height = 0
        self.depth = 1
        self.unknown1 = 0
        self.unknown2 = 0
        self.unknown3 = 0x100
        self.unknown4 = [0] * 18
        self.numMipmaps = 1
        self.padByte = 0
        self.padding = [0] * 22
    
    def fromFile(self, file: BufferedReader):
        self.magic, self.version, self.width, self.height, \
        self.depth, self.unknown1, self.unknown2, self.unknown3 \
        = struct.unpack(">4sIHHHHHH", file.read(0x14))
        
        self.unknown4 = list(struct.unpack("18B", file.read(18)))
        self.numMipmaps, self.padByte = struct.unpack("2B", file.read(2))
        self.padding = list(struct.unpack(">22I", file.read(0x58)))
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(self.magic)
        file.write(struct.pack(">IHHHHHH", self.version, self.width, self.height, \
        self.depth, self.unknown1, self.unknown2, self.unknown3))
        for unk in self.unknown4:
            file.write(struct.pack("B", unk))
        file.write(struct.pack("BB", self.numMipmaps, self.padByte))
        for pad in self.padding:
            file.write(struct.pack(">I", pad))

class CTXRChunk:
    size: int
    data: bytes
    
    def __init__(self):
        self.size = 0
        self.data = b""
    
    def fromFile(self, file: BufferedReader):
        self.size = struct.unpack(">I", file.read(4))[0]
        self.data = file.read(self.size)
        while file.tell() % 0x20 != 0:
            file.read(1)
    
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack(">I", self.size))
        file.write(self.data)
        while file.tell() % 0x20 != 0:
            file.write(b"\0")


class DDS:
    header: DDSHeader
    data: bytes
    
    def __init__(self):
        self.header = DDSHeader()
        self.data = b""
    
    def fromFile(self, file: BufferedReader):
        self.header.fromFile(file)
        
        self.data = file.read()
        
        return self
    
    def convertCTXR(self) -> CTXR:
        ctxr = CTXR()
        ctxr.header.width = self.header.width
        ctxr.header.height = self.header.height
        ctxr.header.numMipmaps = self.header.numMipmaps
        ctxr.header.unknown4 = [0, 0, 0] + [0xff] * 10 + [0, 0, 0, 0, 0]
        ctxr.chunks = []
        
        dataPos = 0
        dataSize = self.header.width * self.header.height * 4
        for i in range(self.header.numMipmaps):
            # print(f"Generating mipmap {i} for CTXR, size {dataSize}...")
            newChunk = CTXRChunk()
            newChunk.size = dataSize
            newChunk.data = self.data[dataPos:dataPos+dataSize]
            ctxr.chunks.append(newChunk)
            dataPos += dataSize
            dataSize //= 4
        
        return ctxr
    
    def writeToFile(self, file: BufferedWriter):
        self.header.writeToFile(file)
        file.write(self.data)

class DDSHeader:
    magic: bytes  # "DDS "
    hdrSize: int # 0x7C
    flags: int
    height: int
    width: int
    pitch: int
    depth: int
    numMipmaps: int
    reserved: bytes  # 44 bytes
    pixelFormat: DDSPixelFormat
    caps: list[int]  # 4 int32s
    reserved2: int
    
    def __init__(self):
        self.magic = b"DDS "
        self.hdrSize = 0x7C
        self.flags = 0
        self.height = 0
        self.width = 0
        self.pitch = 0
        self.depth = 0
        self.numMipmaps = 1
        self.reserved = b"\0" * 44
        self.pixelFormat = DDSPixelFormat()
        self.caps = [0, 0, 0, 0]
        self.reserved2 = 0
    
    def fromFile(self, file: BufferedReader):
        self.magic, self.hdrSize, self.flags, self.height, \
        self.width, self.pitch, self.depth, self.numMipmaps \
        = struct.unpack("<4s7I", file.read(0x20))
        self.reserved = file.read(44)
        self.pixelFormat.fromFile(file)
        self.caps = list(struct.unpack("<4I", file.read(0x10)))
        self.reserved2 = struct.unpack("<I", file.read(4))[0]
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(self.magic)
        file.write(struct.pack("<7I", self.hdrSize, self.flags, self.height, \
        self.width, self.pitch, self.depth, self.numMipmaps))
        file.write(self.reserved)
        self.pixelFormat.writeToFile(file)
        file.write(struct.pack("<5I", self.caps[0], self.caps[1], self.caps[2], self.caps[3], \
        self.reserved2))

class DDSPixelFormat:
    pxlFmtSize: int # 0x20
    flags: int
    fourcc: int
    bitCount: int
    bitMasks: list[int] # RGBA
    
    def __init__(self):
        self.pxlFmtSize = 0x20
        self.flags = 0
        self.fourcc = 0
        self.bitCount = 32
        self.bitMasks = [0xff0000, 0xff00, 0xff, 0xff000000]
    
    def fromFile(self, file: BufferedReader):
        self.pxlFmtSize, self.flags, self.fourcc, self.bitCount \
        = struct.unpack("<4I", file.read(0x10))
        self.bitMasks = list(struct.unpack("<4I", file.read(0x10)))
        
        return self
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<8I", self.pxlFmtSize, self.flags, self.fourcc, self.bitCount, \
        self.bitMasks[0], self.bitMasks[1], self.bitMasks[2], self.bitMasks[3]))


ctxr_lookup_path = path.join(path.dirname(__file__), "ctxrmapping.txt")