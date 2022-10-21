from enum import Enum

class Opcode(Enum):
    getstatic = 0xB2
    ldc = 0x12
    dup = 0x59
    invokevirtual = 0xB6
    invokedynamic = 0xBA
    op_return = 0xB1
    bipush = 0x10
    sipush = 0x11
    nop = 0x0
    
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
    
    istore_0 = 0x3B
    istore_1 = 0x3C
    istore_2 = 0x3D
    istore_3 = 0x3E
    
    fstore_0 = 0x43
    fstore_1 = 0x44
    fstore_2 = 0x45
    fstore_3 = 0x46
    
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
    
    aload_1 = 0x2b
    
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