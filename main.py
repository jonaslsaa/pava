#!/usr/bin/env python3

from dataclasses import dataclass
import sys
import os
import io
from pprint import pprint
from enum import Enum, auto
from typing import Any, List, Tuple, Union
import struct

from jvm_opcode import Opcode

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

class OperandType(Enum):
    OBJECT = auto()
    INT = auto()
    LONG = auto()
    FLOAT = auto()
    DOUBLE = auto()
    REFERENCE = auto()
    RETURN_ADDR = auto()

class ArrayTypeCode(Enum):
    T_BOOLEAN = 4
    T_CHAR = 5
    T_FLOAT = 6
    T_DOUBLE = 7
    T_BYTE = 8
    T_SHORT = 9
    T_INT = 10
    T_LONG = 11

@dataclass
class ExecutionReturnInfo:
    op_count : int

@dataclass(frozen=True, slots=True)
class Operand:
    type : OperandType
    value : Any
    
@dataclass
class JVMClass:
    version : Tuple[int, int]
    constant_pool : List[dict]
    methods : List[dict]
    attributes : List[dict]
    access_flags : List[str]
    this_class : int
    super_class : int

class_access_flags : List[Tuple[str, int]] = [
    ("ACC_PUBLIC"     , 0x0001),
    ("ACC_FINAL"      , 0x0010),
    ("ACC_SUPER"      , 0x0020),
    ("ACC_INTERFACE"  , 0x0200),
    ("ACC_ABSTRACT"   , 0x0400),
    ("ACC_SYNTHETIC"  , 0x1000),
    ("ACC_ANNOTATION" , 0x2000),
    ("ACC_ENUM"       , 0x4000)
]

method_access_flags : List[Tuple[str, int]] = [
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


class AttributeInfoName(Enum):
    BOOTSTRAP_METHOD = b'BootstrapMethods'
    INNER_CLASSES = b'InnerClasses'
    SOURCE_FILE = b'SourceFile'

def parse_flags(value: int, flags: List[Tuple[str, int]]) -> List[str]:
    return [name for (name, mask) in flags if (value & mask) != 0]

def parse_u1(f : Union[io.BytesIO, io.BufferedReader]):
    return struct.unpack('>B', f.read(1))[0]
def parse_i1(f : Union[io.BytesIO, io.BufferedReader]) -> int: return int.from_bytes(f.read(1), 'big')
def parse_i2(f : Union[io.BytesIO, io.BufferedReader]) -> int: return int.from_bytes(f.read(2), 'big')
def parse_i4(f : Union[io.BytesIO, io.BufferedReader]) -> int: return int.from_bytes(f.read(4), 'big')
def parse_f4(f : Union[io.BytesIO, io.BufferedReader]) -> int: return struct.unpack('>f', f.read(4))[0]

def u16_to_i16(v: int) -> int:
    if v & 0x8000:
        return v - 0x10000
    return v

def parse_attributes(f, count) -> list:
    attributes = []
    for j in range(count):
        # attribute_info {
        #     u2 attribute_name_index;
        #     u4 attribute_length;
        #     u1 info[attribute_length];
        # }
        attribute = {}
        attribute['attribute_name_index'] = parse_i2(f)
        attribute_length = parse_i4(f)
        attribute['info'] = f.read(attribute_length)
        attributes.append(attribute)
    return attributes

def parse_attributes_infos(clazz : JVMClass):
    for attr in clazz.attributes:
        attr_name_index = attr['attribute_name_index']
        attr_name = from_cp(clazz, attr_name_index)['bytes']
        attr_info_stream = io.BytesIO(attr['info'])
        attr_info_type = AttributeInfoName(attr_name)
        match attr_info_type:
            case AttributeInfoName.BOOTSTRAP_METHOD:
                attr['info'] = parse_attribute_info_BootstrapMethods(clazz, attr_info_stream)
            case AttributeInfoName.SOURCE_FILE:
                attr['info'] = parse_attribute_info_SourceFile(clazz, attr_info_stream)
            case AttributeInfoName.INNER_CLASSES:
                attr['info'] = parse_attribute_info_InnerClasses(clazz, attr_info_stream)
            case _:
                raise NotImplementedError(f'attribute {attr_name} is not implemented')
        attr['_name'] = attr_name

def parse_attribute_info_BootstrapMethods(clazz : JVMClass, f : io.BytesIO):
    attr = {}
    attr['num_bootstrap_methods'] = parse_i2(f)
    bootstrap_methods = []
    for i in range(attr['num_bootstrap_methods']):
        method = {}
        method['bootstrap_method_ref'] = parse_i2(f)
        method['num_bootstrap_arguments'] = parse_i2(f)
        method['bootstrap_arguments'] = []
        for j in range(method['num_bootstrap_arguments']):
            method['bootstrap_arguments'].append(parse_i2(f))
        bootstrap_methods.append(method)
    attr['bootstrap_methods'] = bootstrap_methods
    return attr

def parse_attribute_info_SourceFile(clazz : JVMClass, f : io.BytesIO):
    attr = {}
    attr['sourcefile_index'] = parse_i2(f)
    return attr

def parse_attribute_info_InnerClasses(clazz : JVMClass, f : io.BytesIO):
    attr = {}
    attr['number_of_classes'] = parse_i2(f)
    classes = []
    for i in range(attr['number_of_classes']):
        cls = {}
        cls['inner_class_info_index'] = parse_i2(f)
        cls['outer_class_info_index'] = parse_i2(f)
        cls['inner_name_index'] = parse_i2(f)
        cls['inner_class_access_flags'] = parse_i2(f)
        classes.append(cls)
    attr['classes'] = classes
    return attr

def print_constant_pool(constant_pool : dict, expand : bool = False):
    def expand_index(index):
        return constant_pool[index - 1]
    for i, cp_info in enumerate(constant_pool):
        expanded = {}
        for k, v in cp_info.items():
            if k.endswith('_index') and expand:
                expanded["__"+k[:-6]+"_"+str(v)] = expand_index(v)
            expanded[k] = v
        print(i+1, expanded['tag'], end=": ")
        pprint(expanded)
    

def parse_constant_pool(f, constant_pool_count) -> list:
    constant_pool = []
    for i in range(constant_pool_count-1):
        cp_info = {}
        tag_byte = parse_i1(f)
        try:
            constant_tag = Constant(tag_byte)
        except ValueError:
            raise NotImplementedError(f"Unknown constant tag {tag_byte} in class file.")
        if Constant.CONSTANT_Methodref == constant_tag:
            cp_info['class_index'] = parse_i2(f)
            cp_info['name_and_type_index'] = parse_i2(f)
        elif Constant.CONSTANT_Class == constant_tag:
            cp_info['name_index'] = parse_i2(f)
        elif Constant.CONSTANT_NameAndType == constant_tag:
            cp_info['name_index'] = parse_i2(f)
            cp_info['descriptor_index'] = parse_i2(f)
        elif Constant.CONSTANT_Utf8 == constant_tag:
            length = parse_i2(f);
            cp_info['bytes'] = f.read(length)
        elif Constant.CONSTANT_Fieldref == constant_tag:
            cp_info['class_index'] = parse_i2(f)
            cp_info['name_and_type_index'] = parse_i2(f)
        elif Constant.CONSTANT_String == constant_tag:
            cp_info['string_index'] = parse_i2(f)
        elif Constant.CONSTANT_InvokeDynamic == constant_tag:
            cp_info['bootstrap_method_attr_index'] = parse_i2(f)
            cp_info['name_and_type_index'] = parse_i2(f)
        elif Constant.CONSTANT_MethodHandle == constant_tag:
            cp_info['reference_kind'] = parse_i1(f)
            cp_info['reference_index'] = parse_i2(f)
        elif Constant.CONSTANT_Float == constant_tag:
            cp_info['bytes'] = parse_f4(f)
        elif Constant.CONSTANT_Integer == constant_tag:
            cp_info['bytes'] = parse_i4(f)
        else:
            raise NotImplementedError(f"Unexpected constant tag {tag_byte} in class file.")
        cp_info['tag'] = constant_tag.name
        constant_pool.append(cp_info)
    return constant_pool

def parse_interfaces(f, interfaces_count):
    interfaces = []
    for i in range(interfaces_count):
        raise NotImplementedError("We don't support interfaces")
    return interfaces

def parse_fields(f, interfaces_count):
    interfaces = []
    for i in range(interfaces_count):
        raise NotImplementedError("We don't support interfaces")
    return interfaces

def parse_class_file(file_path):
    with open(file_path, "rb") as f:
        magic = hex(parse_i4(f))
        if magic != '0xcafebabe':
            raise RuntimeError("Not a Java file: invalid magic number")
        v_minor = parse_i2(f)
        v_major = parse_i2(f)
        version = (v_major, v_minor)
        
        constant_pool_count = parse_i2(f)
        constant_pool = parse_constant_pool(f, constant_pool_count)
        
        access_flags = parse_flags(parse_i2(f), class_access_flags)
        this_class = parse_i2(f)
        super_class = parse_i2(f)
        
        interfaces_count = parse_i2(f)
        interfaces = parse_interfaces(f, interfaces_count)
        fields_count = parse_i2(f)
        fields = parse_fields(f, fields_count)
        
        methods_count = parse_i2(f)
        methods = []
        for i in range(methods_count):
            # u2             access_flags;
            # u2             name_index;
            # u2             descriptor_index;
            # u2             attributes_count;
            # attribute_info attributes[attributes_count];
            method = {}
            method['access_flags'] = parse_flags(parse_i2(f), method_access_flags)
            method['name_index'] = parse_i2(f)
            method['descriptor_index'] = parse_i2(f)
            attributes_count = parse_i2(f)
            method['attributes'] = parse_attributes(f, attributes_count)
            methods.append(method)
        methods = methods
        attributes_count = parse_i2(f)
        attributes = parse_attributes(f, attributes_count)
        clazz = JVMClass(version, constant_pool, methods, attributes, access_flags, this_class, super_class)
        parse_attributes_infos(clazz)
        return clazz

def find_methods_by_name(clazz : JVMClass, name: bytes):
    return [method
            for method in clazz.methods
            if clazz.constant_pool[method['name_index'] - 1]['bytes'] == name]

def find_attributes_by_name(clazz : JVMClass, attributes, name: bytes):
    return [attr
            for attr in attributes
            if clazz.constant_pool[attr['attribute_name_index'] - 1]['bytes'] == name]

def parse_code_info(info: bytes) -> dict:
    code_attribute = {}
    with io.BytesIO(info) as f:
        # Code_attribute {
        #     u2 attribute_name_index;
        #     u4 attribute_length;
        #     u2 max_stack;
        #     u2 max_locals;
        #     u4 code_length;
        #     u1 code[code_length];
        #     u2 exception_table_length;
        #     {   u2 start_pc;
        #         u2 end_pc;
        #         u2 handler_pc;
        #         u2 catch_type;
        #     } exception_table[exception_table_length];
        #     u2 attributes_count;
        #     attribute_info attributes[attributes_count];
        # }
        code_attribute['max_stack'] = parse_i2(f)
        code_attribute['max_locals'] = parse_i2(f)
        code_length = parse_i4(f)
        code_attribute['code'] = f.read(code_length)
        exception_table_length = parse_i2(f)
        for i in range(exception_table_length):
            raise NotImplementedError("We don't support exception tables")
        attributes_count = parse_i2(f)
        code_attribute['attributes'] = parse_attributes(f, attributes_count)
        # NOTE: parsing the code attribute is not finished
        return code_attribute


def FakeStreamPrint(s: str):
    print(s)

def get_name_of_class(clazz, class_index: int) -> str:
    return clazz.constant_pool[clazz.constant_pool[class_index - 1]['name_index'] - 1]['bytes'].decode('utf-8')

def get_name_of_member(clazz, name_and_type_index: int) -> str:
    return clazz.constant_pool[clazz.constant_pool[name_and_type_index - 1]['name_index'] - 1]['bytes'].decode('utf-8')

def from_cp(clazz : JVMClass, index: int) -> dict:
    assert index > 0, "Constant pool index must be positive"
    return clazz.constant_pool[index - 1]

def from_bsm(clazz : JVMClass, index: int) -> dict:
    assert index >= 0, "Bootstrap method index must be non-negative"
    for attr in clazz.attributes: # should be cached, as it is the only bsm
        if attr['_name'] == AttributeInfoName.BOOTSTRAP_METHOD.value:
            return attr['info']['bootstrap_methods'][index]
    raise RuntimeError("Bootstrap method not found")

def pop_expected(stack : List[Operand], expected_type : OperandType):
    assert len(stack) > 0, "Stack underflow"
    if stack[-1].type != expected_type:
        raise RuntimeError(f"Expected {expected_type} on stack, but found {stack[-1].type}")
    return stack.pop()

@dataclass
class Frame:
    stack: List[Operand] # the operand stack
    local_vars: list

def execute_code(clazz : JVMClass, code_attr : dict) -> ExecutionReturnInfo:
    code = code_attr['code']
    frame = Frame(stack=[],
                  local_vars=[None] * code_attr['max_locals'])
    operations_count = 0
    with io.BytesIO(code) as f:
        while f.tell() < len(code):
            opcode_byte = parse_i1(f)
            try:
                opcode = Opcode(opcode_byte)
                operations_count += 1
                print(f"{f.tell():4d} {opcode.name}")
            except ValueError:
                print("Stack trace:")
                pprint(frame.stack)
                raise NotImplementedError(f"Unknown opcode {hex(opcode_byte)}")
            if Opcode.getstatic == opcode:
                index = parse_i2(f)
                fieldref = from_cp(clazz, index)
                name_of_class = get_name_of_class(clazz, fieldref['class_index'])
                name_of_member = get_name_of_member(clazz, fieldref['name_and_type_index'])
                if name_of_class == 'java/lang/System' and name_of_member == 'out':
                    frame.stack.append(Operand(type=OperandType.OBJECT, value=b"FakePrintStream"))
                else:
                    raise NotImplementedError(f"Unsupported member {name_of_class}/{name_of_member} in getstatic instruction")
            elif Opcode.ldc == opcode:
                index = parse_i1(f)
                v = from_cp(clazz, index)
                if v['tag'] == Constant.CONSTANT_String.name:
                    frame.stack.append(Operand(type=OperandType.REFERENCE, value=from_cp(clazz, index)))
                elif v['tag'] == Constant.CONSTANT_Integer.name:
                    frame.stack.append(Operand(type=OperandType.INT, value=v['bytes']))
                elif v['tag'] == Constant.CONSTANT_Float.name:
                    frame.stack.append(Operand(type=OperandType.FLOAT, value=v['bytes']))
                    print(v['bytes'])
                    print("Float", float(v['bytes']))
                else:
                    raise NotImplementedError(f"Unsupported constant {v['tag']} in ldc instruction")
            elif Opcode.invokevirtual == opcode:
                index = parse_i2(f)
                methodref = from_cp(clazz, index)
                name_of_class = get_name_of_class(clazz, methodref['class_index'])
                name_of_member = get_name_of_member(clazz, methodref['name_and_type_index']);
                if name_of_class == 'java/io/PrintStream' and name_of_member == 'println':
                    n = len(frame.stack)
                    if len(frame.stack) < 2:
                        raise RuntimeError('{name_of_class}/{name_of_member} expectes 2 arguments, but provided {n}')
                    obj = frame.stack[-2]
                    if obj.value != b'FakePrintStream':
                        raise NotImplementedError(f"Unsupported stream type {obj.value}")
                    arg = frame.stack[-1]
                    if arg.type == OperandType.REFERENCE:
                        if arg.value['tag'] == 'CONSTANT_String':
                            constant_string = from_cp(clazz, arg.value['string_index'])['bytes']
                            FakeStreamPrint(constant_string.decode('utf-8'))
                        else:
                            raise NotImplementedError(f"println for {arg.value['tag']} is not implemented")
                    elif arg.type == OperandType.INT:
                        FakeStreamPrint(str(arg.value))
                    elif arg.type == OperandType.FLOAT:
                        FakeStreamPrint(str(arg.value))
                    else:
                        raise NotImplementedError(f"Support for {arg.type} is not implemented")
                else:
                    raise NotImplementedError(f"Unknown method {name_of_class}/{name_of_member} in invokevirtual instruction")
            elif Opcode.invokedynamic == opcode:
                indexbyte1 = parse_u1(f)
                indexbyte2 = parse_u1(f)
                cp_index = u16_to_i16((indexbyte1 << 8) + indexbyte2)
                if not (parse_i1(f) == 0 and parse_i1(f) == 0):
                    raise RuntimeError("invokedynamic arguments are not 0")
                dynamic_cp = from_cp(clazz, cp_index)
                assert dynamic_cp['tag'] == Constant.CONSTANT_InvokeDynamic.name, "invokedynamic index is not CONSTANT_InvokeDynamic"
                bootstrap_method_attr = from_bsm(clazz, dynamic_cp['bootstrap_method_attr_index'])
                name_and_type = from_cp(clazz, dynamic_cp['name_and_type_index'])
                print(f"Bootstrap method: {bootstrap_method_attr}")
                print(f"Name and type: {name_and_type}")
                
                exit(0)
                raise NotImplementedError("invokedynamic is not implemented")
            elif Opcode.bipush == opcode:
                byte = parse_i1(f)
                frame.stack.append(Operand(type=OperandType.INT, value=byte))
            elif Opcode.sipush == opcode:
                short = parse_i2(f)
                frame.stack.append(Operand(type=OperandType.INT, value=short))
            elif Opcode.i2f == opcode:
                operand = pop_expected(frame.stack, OperandType.INT)
                frame.stack.append(Operand(type=OperandType.FLOAT, value=float(operand.value)))
            elif Opcode.iadd == opcode:
                v2 = pop_expected(frame.stack, OperandType.INT)
                v1 = pop_expected(frame.stack, OperandType.INT)
                v3 = Operand(type=OperandType.INT, value=v1.value + v2.value)
                frame.stack.append(v3)
            elif Opcode.imul == opcode:
                v2 = pop_expected(frame.stack, OperandType.INT)
                v1 = pop_expected(frame.stack, OperandType.INT)
                v3 = Operand(type=OperandType.INT, value=v1.value * v2.value)
                frame.stack.append(v3)
            elif Opcode.idiv == opcode:
                v2 = pop_expected(frame.stack, OperandType.INT)
                v1 = pop_expected(frame.stack, OperandType.INT)
                v3 = Operand(type=OperandType.INT, value=v1.value // v2.value)
                frame.stack.append(v3)
            elif Opcode.f2i == opcode:
                operand = pop_expected(frame.stack, OperandType.FLOAT)
                frame.stack.append(Operand(type=OperandType.INT, value=int(operand.value)))
            elif Opcode.fadd == opcode:
                v2 = pop_expected(frame.stack, OperandType.FLOAT)
                v1 = pop_expected(frame.stack, OperandType.FLOAT)
                v3 = Operand(type=OperandType.FLOAT, value=v1.value + v2.value)
                frame.stack.append(v3)
            elif Opcode.fsub == opcode:
                v2 = pop_expected(frame.stack, OperandType.FLOAT)
                v1 = pop_expected(frame.stack, OperandType.FLOAT)
                v3 = Operand(type=OperandType.FLOAT, value=v1.value - v2.value)
                frame.stack.append(v3)
            elif Opcode.fmul == opcode:
                v2 = pop_expected(frame.stack, OperandType.FLOAT)
                v1 = pop_expected(frame.stack, OperandType.FLOAT)
                v3 = Operand(type=OperandType.FLOAT, value=v1.value * v2.value)
                frame.stack.append(v3)
            elif Opcode.fdiv == opcode:
                v2 = pop_expected(frame.stack, OperandType.FLOAT)
                v1 = pop_expected(frame.stack, OperandType.FLOAT)
                v3 = Operand(type=OperandType.FLOAT, value=v1.value / v2.value)
                frame.stack.append(v3)
            elif Opcode.aconst_null == opcode:
                frame.stack.append(Operand(type=OperandType.REFERENCE, value=None))
            elif Opcode.istore_0 == opcode:
                frame.local_vars[0] = pop_expected(frame.stack, OperandType.INT)
            elif Opcode.istore_1 == opcode:
                frame.local_vars[1] = pop_expected(frame.stack, OperandType.INT)
            elif Opcode.istore_2 == opcode:
                frame.local_vars[2] = pop_expected(frame.stack, OperandType.INT)
            elif Opcode.istore_3 == opcode:
                frame.local_vars[3] = pop_expected(frame.stack, OperandType.INT)
            elif Opcode.fstore_0 == opcode:
                frame.local_vars[0] = pop_expected(frame.stack, OperandType.FLOAT)
            elif Opcode.fstore_1 == opcode:
                frame.local_vars[1] = pop_expected(frame.stack, OperandType.FLOAT)
            elif Opcode.fstore_2 == opcode:
                frame.local_vars[2] = pop_expected(frame.stack, OperandType.FLOAT)
            elif Opcode.fstore_3 == opcode:
                frame.local_vars[3] = pop_expected(frame.stack, OperandType.FLOAT)
            elif Opcode.iload_0 == opcode:
                frame.stack.append(frame.local_vars[0])
            elif Opcode.iload_1 == opcode:
                frame.stack.append(frame.local_vars[1])
            elif Opcode.iload_2 == opcode:
                frame.stack.append(frame.local_vars[2])
            elif Opcode.iload_3 == opcode:
                frame.stack.append(frame.local_vars[3])
            elif Opcode.fload_0 == opcode:
                frame.stack.append(frame.local_vars[0])
            elif Opcode.fload_1 == opcode:
                frame.stack.append(frame.local_vars[1])
            elif Opcode.fload_2 == opcode:
                frame.stack.append(frame.local_vars[2])
            elif Opcode.fload_3 == opcode:
                frame.stack.append(frame.local_vars[3])
            elif Opcode.iconst_0 == opcode:
                frame.stack.append(Operand(type=OperandType.INT, value=0))
            elif Opcode.iconst_1 == opcode:
                frame.stack.append(Operand(type=OperandType.INT, value=1))
            elif Opcode.iconst_2 == opcode:
                frame.stack.append(Operand(type=OperandType.INT, value=2))
            elif Opcode.iconst_3 == opcode:
                frame.stack.append(Operand(type=OperandType.INT, value=3))
            elif Opcode.iconst_4 == opcode:
                frame.stack.append(Operand(type=OperandType.INT, value=4))
            elif Opcode.iconst_5 == opcode:
                frame.stack.append(Operand(type=OperandType.INT, value=5))
            elif Opcode.lconst_0 == opcode:
                frame.stack.append(Operand(type=OperandType.LONG, value=0))
            elif Opcode.lconst_1 == opcode:
                frame.stack.append(Operand(type=OperandType.LONG, value=1))
            elif Opcode.fconst_0 == opcode:
                frame.stack.append(Operand(type=OperandType.FLOAT, value=0.0))
            elif Opcode.fconst_1 == opcode:
                frame.stack.append(Operand(type=OperandType.FLOAT, value=1.0))
            elif Opcode.fconst_2 == opcode:
                frame.stack.append(Operand(type=OperandType.FLOAT, value=2.0))
            elif Opcode.astore_1 == opcode:
                objectref = frame.stack.pop()
                assert objectref.type in (OperandType.REFERENCE, OperandType.RETURN_ADDR), f"Expected reference/returnAddr, but got {objectref.type}"
                frame.local_vars[1] = objectref
            elif Opcode.aload_1 == opcode:
                objectref = frame.local_vars[1]
                assert objectref.type == OperandType.REFERENCE, f"Expected reference, but got {objectref.type}"
                frame.stack.append(objectref)
                '''
                if_icmpeq = 0x9F
                if_icmpne = 0xA0
                if_icmplt = 0xA1
                if_icmpge = 0xA2
                if_icmpgt = 0xA3
                if_icmple = 0xA4
                '''
            elif Opcode.iinc == opcode:
                index = parse_i1(f)
                const = parse_i1(f)
                frame.local_vars[index] = Operand(type=OperandType.INT, value=frame.local_vars[index].value + const)
            elif opcode in (Opcode.if_icmpeq, Opcode.if_icmpne, Opcode.if_icmplt, Opcode.if_icmpge, Opcode.if_icmpgt, Opcode.if_icmple):
                v2 = pop_expected(frame.stack, OperandType.INT)
                v1 = pop_expected(frame.stack, OperandType.INT)
                branchbyte1 = parse_u1(f) # unsigned byte
                branchbyte2 = parse_u1(f)
                do_branch = False
                match opcode:
                    case Opcode.if_icmpeq:
                        if v1.value == v2.value: do_branch = True
                    case Opcode.if_icmpne:
                        if v1.value != v2.value: do_branch = True
                    case Opcode.if_icmplt:
                        if v1.value < v2.value: do_branch = True
                    case Opcode.if_icmpge:
                        if v1.value >= v2.value: do_branch = True
                    case Opcode.if_icmpgt:
                        if v1.value > v2.value: do_branch = True
                    case Opcode.if_icmple:
                        if v1.value <= v2.value: do_branch = True
                    case _:
                        raise Exception(f"Unknown if_icmp<cond> {opcode}")
                if do_branch:
                    branch_offset = u16_to_i16(branchbyte1 << 8 | branchbyte2)
                    actual_offset = branch_offset - 3 # because we already read 3 bytes
                    f.seek(actual_offset, 1) # 1 means relative to current position
            elif Opcode.goto == opcode:
                branchbyte1 = parse_u1(f) # unsigned byte
                branchbyte2 = parse_u1(f)
                branch_offset = u16_to_i16(branchbyte1 << 8 | branchbyte2)
                actual_offset = branch_offset - 3
                f.seek(actual_offset, 1)
            elif Opcode.newarray == opcode:
                count = pop_expected(frame.stack, OperandType.INT)
                atype = parse_u1(f)
                arr_type = None
                arr_default = None
                match ArrayTypeCode(atype):
                    case ArrayTypeCode.T_INT:
                        arr_type = OperandType.INT
                        arr_default = 0
                    case _:
                        raise NotImplementedError(f"newarray for atype {atype}")
                array = [Operand(type=arr_type, value=arr_default) for _ in range(count.value)]
                arrayref = Operand(type=OperandType.REFERENCE, value=array)
                frame.stack.append(arrayref)
            elif Opcode.arraylength == opcode:
                arrayref = pop_expected(frame.stack, OperandType.REFERENCE)
                frame.stack.append(Operand(type=OperandType.INT, value=len(arrayref.value)))
            elif Opcode.iaload == opcode:
                index = pop_expected(frame.stack, OperandType.INT)
                arrayref = pop_expected(frame.stack, OperandType.REFERENCE)
                frame.stack.append(arrayref.value[index.value])
            elif Opcode.iastore == opcode:
                value = pop_expected(frame.stack, OperandType.INT)
                index = pop_expected(frame.stack, OperandType.INT)
                arrayref = pop_expected(frame.stack, OperandType.REFERENCE)
                arrayref.value[index.value] = value
            elif Opcode.dup == opcode:
                v = frame.stack.pop()
                frame.stack.append(v)
                frame.stack.append(v)
            elif Opcode.op_return == opcode:
                return ExecutionReturnInfo(op_count=operations_count)
            elif Opcode.nop == opcode:
                pass
            else:
                raise NotImplementedError(f"Opcode {opcode} is not implemented")
            
            #print(f.tell(), '==>')
            #print(frame.stack)
            #print("Local variables:")
            #pprint(frame.local_vars)
        raise Exception("Reached end of method without an op_return")

if __name__ == '__main__':
    program, *args = sys.argv
    if len(args) != 1:
        print(f"Usage: {program} <path/to/Main.class>")
        print(f"ERROR: no path to Main.class was provided")
        exit(1)
    file_path, *args = args
    if not os.path.exists(file_path) and not file_path.endswith('.class'):
        file_path += '.class'
    if not os.path.exists(file_path):
        print(f"ERROR: file {file_path} does not exist")
        exit(1)
    clazz = parse_class_file(file_path)
    [main] = find_methods_by_name(clazz, b'main')
    [code] = find_attributes_by_name(clazz, main['attributes'], b'Code')
    code_attribute = parse_code_info(code['info'])
    
    #exec_info = execute_code(clazz, code_attribute)
    #print(f"Executed {exec_info.op_count} operations.")
    
    #print_constant_pool(clazz.constant_pool, expand=False)
    #print('Attributes:')
    #pprint(clazz.attributes)
    #print('Methods:')
    #pprint(clazz.methods)