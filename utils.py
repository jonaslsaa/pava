from typing import Any, List, Tuple, Union
import io
import struct


def parse_u1(f : Union[io.BytesIO, io.BufferedReader]): # char
    return struct.unpack('>B', f.read(1))[0]
def parse_u2(f : Union[io.BytesIO, io.BufferedReader]) -> int: # short
    return struct.unpack('>H', f.read(2))[0]
def parse_i1(f : Union[io.BytesIO, io.BufferedReader]) -> int: return int.from_bytes(f.read(1), 'big')
def parse_i2(f : Union[io.BytesIO, io.BufferedReader]) -> int: return int.from_bytes(f.read(2), 'big')
def parse_i4(f : Union[io.BytesIO, io.BufferedReader]) -> int: return int.from_bytes(f.read(4), 'big') # int
def parse_f4(f : Union[io.BytesIO, io.BufferedReader]) -> int: return struct.unpack('>f', f.read(4))[0]

def u16_to_i16(v: int) -> int:
    if v & 0x8000:
        return v - 0x10000
    return v