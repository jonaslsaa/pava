#!/usr/bin/env python3

from dataclasses import dataclass
import sys
import os
import io
from pprint import pprint
from enum import Enum, auto
from typing import Any, List, Tuple, Union
import struct

from jvmconsts import *
from jvmparser import JVMClass, parse_class_file, parse_code_info, find_attributes_by_name
from jvmparser import find_methods_by_name, print_constant_pool, get_name_of_class, get_name_of_member, from_bsm, from_cp
from utils import *

class OperandType(Enum):
    OBJECT = auto()
    INT = auto()
    LONG = auto()
    FLOAT = auto()
    DOUBLE = auto()
    REFERENCE = auto()
    RETURN_ADDR = auto()

@dataclass
class ExecutionReturnInfo:
    op_count : int

@dataclass(frozen=True, slots=True)
class Operand:
    type : OperandType
    value : Any

def FakeStreamPrint(s: str):
    print(s)

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
    
    print_constant_pool(clazz.constant_pool, expand=False)
    #print('Attributes:')
    #pprint(clazz.attributes)
    #print('Methods:')
    #pprint(clazz.methods)