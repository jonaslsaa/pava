from enum import Enum, auto
from typing import Any, List, Tuple, Union

class Constant(Enum):
    CONSTANT_Class              = 7
    CONSTANT_Fieldref           = 9
    CONSTANT_Methodref          = 10
    CONSTANT_InterfaceMethodref = 11
    CONSTANT_String             = 8
    CONSTANT_Integer            = 3
    CONSTANT_Float              = 4
    CONSTANT_Long               = 5
    CONSTANT_Double             = 6
    CONSTANT_NameAndType        = 12
    CONSTANT_Utf8               = 1
    CONSTANT_MethodHandle       = 15
    CONSTANT_MethodType         = 16
    CONSTANT_InvokeDynamic      = 18

class ArrayTypeCode(Enum):
    T_BOOLEAN = 4
    T_CHAR = 5
    T_FLOAT = 6
    T_DOUBLE = 7
    T_BYTE = 8
    T_SHORT = 9
    T_INT = 10
    T_LONG = 11

CLASS_ACCESS_FLAGS : List[Tuple[str, int]] = [
    ("ACC_PUBLIC"     , 0x0001),
    ("ACC_FINAL"      , 0x0010),
    ("ACC_SUPER"      , 0x0020),
    ("ACC_INTERFACE"  , 0x0200),
    ("ACC_ABSTRACT"   , 0x0400),
    ("ACC_SYNTHETIC"  , 0x1000),
    ("ACC_ANNOTATION" , 0x2000),
    ("ACC_ENUM"       , 0x4000)
]

METHOD_ACCESS_FLAGS : List[Tuple[str, int]] = [
    ("ACC_PUBLIC", 0x0001),
    ("ACC_PRIVATE", 0x0002),
    ("ACC_PROTECTED", 0x0004),
    ("ACC_STATIC", 0x0008),
    ("ACC_FINAL", 0x0010),
    ("ACC_SYNCHRONIZED", 0x0020),
    ("ACC_BRIDGE", 0x0040),
    ("ACC_VARARGS", 0x0080),
    ("ACC_NATIVE", 0x0100),
    ("ACC_ABSTRACT", 0x0400),
    ("ACC_STRICT", 0x0800),
    ("ACC_SYNTHETIC", 0x1000),
]

class Opcode(Enum):
    getstatic = 0xB2
    ldc = 0x12
    dup = 0x59
    invokevirtual = 0xB6
    invokedynamic = 0xBA
    invokespecial = 0xB7
    invokestatic = 0xB8
    return_op = 0xB1
    bipush = 0x10
    sipush = 0x11
    nop = 0x0
    
    ireturn = 0xAC
    freturn = 0xAE
    areturn = 0xB0
    lreturn = 0xAD
    dreturn = 0xAF
    
    i2f = 0x86
    iadd = 0x60
    imul = 0x68
    idiv = 0x6C
    isub = 0x64
    iinc = 0x84
    
    f2i = 0x8B
    fadd = 0x62
    fsub = 0x66
    fmul = 0x6A
    fdiv = 0x6E
    
    aconst_null = 0x1
    iconst_0 = 0x3
    iconst_1 = 0x4
    iconst_2 = 0x5
    iconst_3 = 0x6
    iconst_4 = 0x7
    iconst_5 = 0x8
    
    lconst_0 = 0x9
    lconst_1 = 0xa
    
    fconst_0 = 0xB
    fconst_1 = 0xC
    fconst_2 = 0xD
    
    istore = 0x36
    istore_0 = 0x3B
    istore_1 = 0x3C
    istore_2 = 0x3D
    istore_3 = 0x3E
    
    fstore_0 = 0x43
    fstore_1 = 0x44
    fstore_2 = 0x45
    fstore_3 = 0x46
    
    iload = 0x15
    iload_0 = 0x1A
    iload_1 = 0x1B
    iload_2 = 0x1C
    iload_3 = 0x1D
    
    fload_0 = 0x22
    fload_1 = 0x23
    fload_2 = 0x24
    fload_3 = 0x25
    
    iaload = 0x2E
    iastore = 0x4F 
    astore_1 = 0x4C
    
    aload_0 = 0x2A
    aload_1 = 0x2b
    aload_2 = 0x2c
    aload_3 = 0x2d
    
    # Control flow
    if_icmpeq = 0x9F
    if_icmpne = 0xA0
    if_icmplt = 0xA1
    if_icmpge = 0xA2
    if_icmpgt = 0xA3
    if_icmple = 0xA4
    goto = 0xA7
    
    newarray = 0xBC
    arraylength = 0xBE