from __future__ import annotations
from io import BufferedReader, BufferedWriter
import struct
from os import path


class TRI:
    header: TRIHeader
    textures: List[TRIEntry]
    
    def fromFile(self, file: BufferedReader):
        self.header = TRIHeader().fromFile(file)
        
        self.textures = [
            TRIEntry().fromFile(file)
            for _ in range(self.header.numTexture)
        ]
        
        return self
    
    def dumpTextures(self, extract_dir: str):
        textureBuffer = self.header.initPartialProcessBuffer(0)
        clutBuffer = self.header.initPartialProcessBuffer(1)
        
        for entry in self.textures:
            print("Dumping texture %d.tga" % entry.texID)
            entry.dumpTexture(extract_dir, textureBuffer, clutBuffer)
    
    def dumpById(self, extract_dir: str, texID: int):
        for entry in self.textures:
            if entry.texID == texID:
                textureBuffer = self.header.initPartialProcessBuffer(0)
                clutBuffer = self.header.initPartialProcessBuffer(1)
                return entry.dumpTexture(extract_dir, textureBuffer, clutBuffer)
        return None
    
    def dumpByIndex(self, extract_dir: str, index: int):
        if not (0 <= index < len(self.textures)):
            return None
        
        textureBuffer = self.header.initPartialProcessBuffer(0)
        clutBuffer = self.header.initPartialProcessBuffer(1)
        
        return self.textures[index].dumpTexture(extract_dir, textureBuffer, clutBuffer)
        
    
    def packTextures(self):
        print("TRI edit TODO")
        return
    
    def writeToFile(self, file: BufferedWriter):
        print("TRI write TODO")
        return


class TRIHeader:
    pad: int
    width: int
    height: int
    clutHeight: int
    numTexture: int
    pad2: int
    imageOffset: int
    clutOffset: int
    
    rawData: List[int] # technically uints/bytes/whatever
    rawClut: List[int]
    
    def fromFile(self, file: BufferedReader):
        self.pad, self.width, self.height, self.clutHeight, \
        self.numTexture, self.pad2, self.imageOffset, self.clutOffset \
        = struct.unpack("<IiiIiIii", file.read(0x20))
        
        returnPos = file.tell()
        file.seek(self.imageOffset)
        self.rawData = list(struct.unpack(f"<{64 * self.height}I", file.read(4 * 64 * self.height)))
        
        file.seek(self.clutOffset)
        self.rawClut = list(struct.unpack(f"<{64 * self.clutHeight}I", file.read(4 * 64 * self.clutHeight)))
        
        file.seek(returnPos)
        
        return self
    
    blockArrangement: List[int] = [
     0,  1,  4,  5, 16, 17, 20, 21,
     2,  3,  6,  7, 18, 19, 22, 23,
     8,  9, 12, 13, 24, 25, 28, 29,
    10, 11, 14, 15, 26, 27, 30, 31]
    
    wordArrangement: List[int] = [
     0,  1,  4,  5,  8,  9, 12, 13,
     2,  3,  6,  7, 10, 11, 14, 15]
    
    # https://github.com/Jayveer/MGS-Master-Collection-Noesis/blob/master/ps2/PS2Textures.cpp
    def initPartialProcessBuffer(self, mode):
        if mode == 0:
            rawData = self.rawData
            height = self.height
        elif mode == 1:
            rawData = self.rawClut
            height = self.clutHeight
        
        result = [0] * (1024 * 1024)
        i = 0
        for y in range(height):
            for x in range(64):
                page = y // 32
                
                px = x
                py = y % 32
                blockX = px // 8
                blockY = py // 8
                block = TRIHeader.blockArrangement[blockX + blockY * 8]
                
                bx = x % 8
                by = y % 8
                column = by // 2
                cx = bx
                cy = y % 2
                word = TRIHeader.wordArrangement[cx + cy * 8]
                
                result[page * 2048 + block * 64 + column * 16 + word] = rawData[i]
                i += 1
        
        return result
    
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<IiiIiIii", \
        self.pad, self.width, self.height, self.clutHeight, \
        self.numTexture, self.pad2, self.imageOffset, self.clutOffset))

class TRIEntry:
    uOffset: float
    vOffset: float
    uScale: float
    vScale: float
    texID: int
    pad: List[int] # 11 entries
    unknownA: int
    unknownB: int
    unknownC: int
    pad2: int
    unknownD: int
    unknownE: int
    unknownF: int
    pad3: int
    registerInfo1: GsTex0
    unknownG: int
    unknownH: int
    registerInfo2: GsTex0
    unknownI: List[int] # 10 entries
    u1: float
    v1: float
    u2: float
    v2: float
    u3: float
    v3: float
    pad4: int
    pad5: int
    
    def fromFile(self, file: BufferedReader):
        self.uOffset, self.vOffset, self.uScale, self.vScale, \
        self.texID = struct.unpack("<ffffI", file.read(0x14))
        self.pad = list(struct.unpack("<11I", file.read(0x2C)))
        self.unknownA, self.unknownB, self.unknownC, self.pad2, \
        self.unknownD, self.unknownE, self.unknownF, self.pad3 \
        = struct.unpack("<8I", file.read(0x20))
        self.registerInfo1 = GsTex0().fromFile(file)
        self.unknownG, self.unknownH = struct.unpack("<II", file.read(8))
        self.registerInfo2 = GsTex0().fromFile(file)
        self.unknownI = list(struct.unpack("<10I", file.read(0x28)))
        self.u1, self.v1, self.u2, self.v2, \
        self.u3, self.v3, self.pad4, self.pad5 \
        = struct.unpack("<6f2I", file.read(0x20))
        return self
    
    def dumpTexture(self, extract_dir: str, textureBuffer: List[int], clutBuffer: List[int]):
        imageWidth = int(2**self.registerInfo2.tw)
        imageHeight = int(2**self.registerInfo2.th)
        
        texX = int(self.uOffset * imageWidth)
        texY = int(self.vOffset * imageHeight)
        texWidth = int(self.uScale * imageWidth + 1)
        texHeight = int(self.vScale * imageHeight + 1)
        
        #texBuffer = [0] * (1024 * 1024)
        #clutBuffer = [0] * (1024 * 1024)
        
        if self.registerInfo2.psm == 0x13:
            clutWidth = 16
            clutHeight = 16
            size = texWidth * texHeight
            texBuffer = readTexPSMT8(self.registerInfo2.tbp0, self.registerInfo2.tbw, texX, texY, texWidth, texHeight, textureBuffer)
            print("PSM 0x13")
        elif self.registerInfo2.psm == 0x14:
            clutWidth = 8
            clutHeight = 2
            size = texWidth * texHeight // 2
            texBuffer = readTexPSMT4(self.registerInfo2.tbp0, self.registerInfo2.tbw, texX, texY, texWidth, texHeight, textureBuffer)
            print("PSM 0x14, alpha", self.registerInfo2.has_alpha)
        else:
            print(f"Failed to export texture {self.texID}.tga: Unrecognized PSM {hex(self.registerInfo2.psm)}")
            return None
        
        if self.registerInfo2.cpsm == 0 and self.registerInfo2.csm == 0:
            specialClutBuffer = readTexPSMCT32(self.registerInfo2.cbp, 1, self.registerInfo2.csa * 8, 0, clutWidth, clutHeight, clutBuffer)
            if self.registerInfo2.psm == 0x13:
                specialClutBuffer = unswizzleClut(specialClutBuffer)
            
            if all([x == 0 for x in specialClutBuffer]):
                print("Invalid clut! CBP: %d, CSA: %d" % (self.registerInfo2.cbp, self.registerInfo2.csa))
                specialClutBuffer = readTexPSMCT32(0, 1, 0, 0, clutWidth, clutHeight, clutBuffer)
            else:
                print("Valid clut: CBP: %d, CSA: %d" % (self.registerInfo2.cbp, self.registerInfo2.csa))
        else:
            #specialClutBuffer = [0] * (1024 * 1024)
            print("Failed to export texture %d.tga: Unrecognized CPSM %d CSM %d" % (self.texID, self.registerInfo2.cpsm, self.registerInfo2.csm))
            return None
        
        pixels = paintPixels(specialClutBuffer, texBuffer, texWidth, texHeight)
        
        if pixels is None:
            print("Failed to export texture %d.tga: paintPixels error" % self.texID)
            return None
        
        out_path = path.join(extract_dir, "%d.tga" % self.texID)
        
        with open(out_path, "wb") as f:
            f.write(b"\x00\x00\x02\x00") # magic
            f.write(b"\x00\x00\x00\x00\x00\x00\x00\x00") # padding
            f.write(struct.pack("<hh", texWidth, texHeight))
            f.write(b"\x20\x20") # also magic I guess
            f.write(pixels)
        
        return out_path
        
    
    def writeToFile(self, file: BufferedWriter):
        file.write(struct.pack("<ffffI", \
        self.uOffset, self.vOffset, self.uScale, self.vScale, \
        self.texID))
        
        for i in range(11):
            file.write(struct.pack("<I", self.pad[i]))
        file.write(struct.pack("<8I", \
        self.unknownA, self.unknownB, self.unknownC, self.pad2, \
        self.unknownD, self.unknownE, self.unknownF, self.pad3))
        
        self.registerInfo1.writeToFile(file)
        file.write(struct.pack("<II", self.unknownG, self.unknownH))
        
        self.registerInfo2.writeToFile(file)
        for i in range(10):
            file.write(struct.pack("<I", self.unknownI[i]))
        file.write(struct.pack("<6f2I", \
        self.u1, self.v1, self.u2, self.v2, \
        self.u3, self.v3, self.pad4, self.pad5))


class GsTex0:
    # TBP0 : 14; // Texture Buffer Base Pointer (Address/256)
	# TBW : 6; // Texture Buffer Width (Texels/64)
	# PSM : 6; // Pixel Storage Format (0 = 32bit RGBA)
	# TW : 4; // width = 2^TW
	# TH : 4; // height = 2^TH
	# TCC : 1; // 0 = RGB, 1 = RGBA
	# TFX : 2; // TFX  - Texture Function (0=modulate, 1=decal, 2=hilight, 3=hilight2)
	# CBP : 14; // CLUT Buffer Base Pointer
	# CPSM : 4; // CLUT Storage Format
	# CSM : 1; // CLUT Storage Mode
	# CSA : 5; // CLUT Offset
	# CLD : 3; // CLUT Load Control
    rawData: int
    
    tbp0: int
    tbw: int
    psm: int
    tw: int
    th: int
    has_alpha: bool
    tfx: int
    cbp: int
    cpsm: int
    csm: int
    csa: int
    cld: int
    
    def getBits(self, start, count):
        mask = (1 << count) - 1
        mask <<= start
        return (self.rawData & mask) >> start
    
    def fromFile(self, file: BufferedReader):
        self.rawData = struct.unpack("<Q", file.read(8))[0]
        self.tbp0 = self.getBits(0, 14)
        self.tbw = self.getBits(14, 6)
        self.psm = self.getBits(20, 6)
        self.tw = self.getBits(26, 4)
        self.th = self.getBits(30, 4)
        self.has_alpha = self.getBits(34, 1) == 1
        self.tfx = self.getBits(35, 2)
        self.cbp = self.getBits(37, 14)
        self.cpsm = self.getBits(51, 4)
        self.csm = self.getBits(55, 1)
        self.csa = self.getBits(56, 5)
        self.cld = self.getBits(61, 3)
        return self
    
    def putBits(self, start, count, val):
        mask = (1 << count) - 1
        mask <<= start
        self.rawData &= ~mask
        self.rawData |= val << start
    
    def writeToFile(self, file: BufferedWriter):
        self.putBits(0, 14, self.tbp0)
        self.putBits(14, 6, self.tbw)
        self.putBits(20, 6, self.psm)
        self.putBits(26, 4, self.tw)
        self.putBits(30, 4, self.th)
        self.putBits(34, 1, 1 if self.has_alpha else 0)
        self.putBits(35, 2, self.tfx)
        self.putBits(37, 14, self.cbp)
        self.putBits(51, 4, self.cpsm)
        self.putBits(55, 1, self.csm)
        self.putBits(56, 5, self.csa)
        self.putBits(61, 3, self.cld)
        file.write(struct.pack("<Q", self.rawData))


block8Layout = [
     0, 1, 4, 5,16,17,20,21,
     2, 3, 6, 7,18,19,22,23,
     8, 9,12,13,24,25,28,29,
    10,11,14,15,26,27,30,31]

columnWord8Layout = [
    [
         0, 1, 4, 5, 8, 9,12,13,  0, 1, 4, 5, 8, 9,12,13,
         2, 3, 6, 7,10,11,14,15,  2, 3, 6, 7,10,11,14,15,

         8, 9,12,13, 0, 1, 4, 5,  8, 9,12,13, 0, 1, 4, 5,
        10,11,14,15, 2, 3, 6, 7, 10,11,14,15, 2, 3, 6, 7
	],
	[
         8, 9,12,13, 0, 1, 4, 5,  8, 9,12,13, 0, 1, 4, 5,
        10,11,14,15, 2, 3, 6, 7, 10,11,14,15, 2, 3, 6, 7,

         0, 1, 4, 5, 8, 9,12,13,  0, 1, 4, 5, 8, 9,12,13,
         2, 3, 6, 7,10,11,14,15,  2, 3, 6, 7,10,11,14,15
    ]]

columnByte8Layout = [
    0, 2,
    1, 3]

def readTexPSMT8(dbp: int, dbw: int, dsax: int, dsay: int, rrw: int, rrh: int, halfBuffer: List[int]):
    dbw >>= 1
    dbp <<= 6
    
    i = 0
    outBuf = [[0, 0, 0, 0] for x in range(rrh * rrw)] 
    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 128
            pageY = y // 64
            page = pageX + pageY * dbw
            
            px = x % 128
            py = y % 64
            blockX = px // 16
            blockY = py // 16
            block = block8Layout[blockX + blockY * 8]
            
            bx = px % 16
            by = py % 16
            column = by // 4
            
            cx = bx
            cy = by % 4
            word = columnWord8Layout[column & 1][cx + cy * 16]
            
            dx = cx // 8
            dy = cy // 2
            byt = columnByte8Layout[dx + dy * 2]
            
            val = halfBuffer[dbp + page * 2048 + block * 64 + column * 16 + word]
            myByte = struct.unpack("BBBB", struct.pack("<I", val))[byt]
            outBuf[i // 4][i % 4] = myByte
            i += 1
    
    return [struct.unpack("<I", struct.pack("BBBB", x[0], x[1], x[2], x[3]))[0] for x in outBuf]


block4Layout = [
     0,  2,  8, 10,
     1,  3,  9, 11,
     4,  6, 12, 14,
     5,  7, 13, 15,
    16, 18, 24, 26,
    17, 19, 25, 27,
    20, 22, 28, 30,
    21, 23, 29, 31]

columnWord4Layout = [
    [ 0, 1, 4, 5, 8, 9,12,13] * 4 +
    [ 2, 3, 6, 7,10,11,14,15] * 4 +
    [ 8, 9,12,13, 0, 1, 4, 5] * 4 +
    [10,11,14,15, 2, 3, 6, 7] * 4,
    
    [ 8, 9,12,13, 0, 1, 4, 5] * 4 +
    [10,11,14,15, 2, 3, 6, 7] * 4 +
    [ 0, 1, 4, 5, 8, 9,12,13] * 4 +
    [ 2, 3, 6, 7,10,11,14,15] * 4]

columnByte4Layout = [
    0, 2, 4, 6,
    1, 3, 5, 7]

def splitToFourBits(val):
    myBytes = struct.unpack("BBBB", struct.pack("<I", val))
    result = []
    for byt in list(myBytes):
        result += byt & 0xf
        result += (byt & 0xf0) >> 4
    return result

def mergeFromFourBits(vals):
    pass

def readTexPSMT4(dbp: int, dbw: int, dsax: int, dsay: int, rrw: int, rrh: int, halfBuffer: List[int]):
    dbw >>= 1
    dbp <<= 6
    # TODO: make this the 4-bit version
    i = 0
    outBuf = [([0] * 8) for x in range(rrh * rrw)]
    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 128
            pageY = y // 128
            page = pageX + pageY * dbw
            
            px = x % 128
            py = y % 128
            blockX = px // 32
            blockY = py // 16
            block = block4Layout[blockX + blockY * 4]
            
            bx = px % 32
            by = py % 16
            column = by // 4
            
            cx = bx
            cy = by % 4
            word = columnWord4Layout[column & 1][cx + cy * 32]
            
            dx = cx // 8
            dy = cy // 2
            byt = columnByte4Layout[dx + dy * 4]
            
            val = halfBuffer[dbp + page * 2048 + block * 64 + column * 16 + word]
            myByte = struct.unpack("BBBB", struct.pack("<I", val))[byt // 2]
            if byt % 2 == 1: # hi halfbyte
                outBuf[i // 8][i % 8] |= (myByte & 0xf0) >> 4
            else: # lo halfbyte
                outBuf[i // 8][i % 8] |= myByte & 0xf
            
            i += 1
    
    trueOutBuf = []
    for x in outBuf:
        myRearrange = struct.unpack("<II", struct.pack("BBBBBBBB", x[0], x[1], x[2], x[3], x[4], x[5], x[6], x[7]))
        trueOutBuf.append(myRearrange[0])
        trueOutBuf.append(myRearrange[1])
    
    return trueOutBuf


def paintPixels(clut: List[int], pixels: List[int], width: int, height: int) -> bytes:
    sizeOut = width * height * 4
    texture = b""
    print("There are %d pixels" % len(pixels))
    clut = [list(struct.unpack("BBBB", struct.pack("<I", x))) for x in clut] # RGBA
    pixels = [list(struct.unpack("BBBB", struct.pack("<I", x))) for x in pixels]
    for y in range(height):
        for x in range(width):
            pixelPos = x + y * width
            pixel = pixels[pixelPos // 4][pixelPos % 4]
            clutPix = clut[pixel]
            #print(clutPix[2], clutPix[1], clutPix[0], ((clutPix[3] * 255) // 0x80))
            if clutPix[3] > 0x80:  # Invalid clut
                print("paintPixels: Invalid alpha in clut at %d, %d" % (x, y))
                return None
            texture += struct.pack("BBBB", \
            clutPix[2], clutPix[1], clutPix[0], (clutPix[3] * 0xff) // 0x80)
            #clutPix[2], clutPix[1], clutPix[0], clutPix[3])
    return texture


blockArrangement32: List[int] = [
 0,  1,  4,  5, 16, 17, 20, 21,
 2,  3,  6,  7, 18, 19, 22, 23,
 8,  9, 12, 13, 24, 25, 28, 29,
10, 11, 14, 15, 26, 27, 30, 31]

wordArrangement32: List[int] = [
 0,  1,  4,  5,  8,  9, 12, 13,
 2,  3,  6,  7, 10, 11, 14, 15]

def readTexPSMCT32(dbp: int, dbw: int, dsax: int, dsay: int, rrw: int, rrh: int, halfBuffer: List[int]):
    dbp <<= 6
    result = [0] * (rrh * rrw)
    i = 0
    for y in range(dsay, dsay + rrh):
        for x in range(dsax, dsax + rrw):
            pageX = x // 64
            pageY = y // 32
            page = pageX + pageY * dbw
            
            px = x % 64
            py = y % 32
            blockX = px // 8
            blockY = py // 8
            block = blockArrangement32[blockX + blockY * 8]
            
            bx = x % 8
            by = y % 8
            column = by // 2
            cx = bx
            cy = y % 2
            word = wordArrangement32[cx + cy * 8]
            
            result[i] = halfBuffer[dbp + page * 2048 + block * 64 + column * 16 + word]
            i += 1
    
    return result

def unswizzleClut(buffer: List[int]):
    for i in range(1, 30, 4):
        # swap sections of 32 bytes (8 ints)
        j = i + 1
        for k in range(8):
            buffer[i*8+k], buffer[j*8+k] = buffer[j*8+k], buffer[i*8+k]
    return buffer