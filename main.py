#!/usr/bin/env python3

from dataclasses import dataclass
import sys
import os
import io
from pprint import pprint
from enum import Enum, auto
from time import perf_counter_ns
from typing import Any, List, Tuple, Dict

from jvmconsts import *
from jvmparser import AttributeInfoName, JVMClassFile, get_type_of_member, parse_class_file, parse_flags
from jvmparser import print_constant_pool, get_name_of, get_name_of, from_bsm, from_cp
from utils import *

class OperandType(Enum):
    OBJECT = auto()
    INT = auto()
    LONG = auto()
    FLOAT = auto()
    DOUBLE = auto()
    REFERENCE = auto()
    RETURN_ADDR = auto()
    VOID = auto()

@dataclass(frozen=True, slots=True)
class Operand:
    type : OperandType
    value : Any
    
@dataclass
class ExecutionReturnInfo:
    op_count : int
    return_value : Operand | None = None
    
@dataclass
class RuntimeClass:
    class_file: JVMClassFile
    static_fields : Dict[str, Operand]

def sig_char_to_operand_types(char : str):
    if char == 'I':
        return OperandType.INT
    elif char == 'J':
        return OperandType.LONG
    elif char == 'F':
        return OperandType.FLOAT
    elif char == 'D':
        return OperandType.DOUBLE
    elif char == 'V':
        return OperandType.VOID
    elif char == 'L':
        return OperandType.REFERENCE
    return None

#ex: (II)I -> ((OperandType.INT, OperandType.INT), OperandType.INT)
# READ: https://stackoverflow.com/questions/9909228/what-does-v-mean-in-a-class-signature
def parse_signature(sig : str) -> Tuple[List[OperandType], OperandType]:
    sig = sig[1:] # skip the '('
    # Parse the arguments
    args : List[OperandType] = []
    while sig[0] != ')':
        _type = sig_char_to_operand_types(sig[0])
        if _type is None:
            raise RuntimeError(f"Unknown signature type: {sig[0]}")
        args.append(_type)
        sig = sig[1:]
    sig = sig[1:] # skip the ')'
    # Parse the return type
    return_type = sig_char_to_operand_types(sig[0])
    if return_type is None:
        raise RuntimeError(f"Unknown signature return type: {sig[0]}")
    sig = sig[1:]
    assert len(sig) == 0, "Invalid signature: trailing characters"
    return (args, return_type)

def pop_expected(stack : List[Operand], expected_type : OperandType):
    assert len(stack) > 0, "Stack underflow"
    if stack[-1].type != expected_type:
        raise RuntimeError(f"Expected {expected_type} on stack, but found {stack[-1].type}")
    return stack.pop()

def initialize_runtime_class(class_file: JVMClassFile, loaded_classes: Dict[str, JVMClassFile], runtime_classes: Dict[str, RuntimeClass]):
    # Get name of this class
    class_name = get_name_of(class_file.constant_pool, class_file.this_class)
    if class_name in runtime_classes:
        return # Already initialized
    # Initialize the static fields dictionary with default values based on type
    static_fields = {}

    # Iterate over all fields to set default values (e.g., int -> 0)
    for field_info in class_file.fields:
        field_name = get_name_of(class_file.constant_pool, field_info['name_index'])
        field_type = get_type_of_member(class_file.constant_pool, field_info['descriptor_index'])

        access_flags = parse_flags(field_info['access_flags'], METHOD_ACCESS_FLAGS)
        if 'ACC_STATIC' in access_flags:
            # Assign default values
            if field_type == 'I':  # int
                static_fields[field_name] = Operand(OperandType.INT, 0)
            elif field_type == 'F':  # float
                static_fields[field_name] = Operand(OperandType.FLOAT, 0.0)
            elif field_type == 'J':  # long
                static_fields[field_name] = Operand(OperandType.LONG, 0)
            elif field_type == 'D':  # double
                static_fields[field_name] = Operand(OperandType.DOUBLE, 0.0)
            elif field_type.startswith('L') or field_type.startswith('['):  # object or array reference
                static_fields[field_name] = Operand(OperandType.REFERENCE, None)
            else:
                raise NotImplementedError(f"Static field type {field_type} not implemented")

    # Create the RuntimeClass with default-initialized static fields
    runtime_class = RuntimeClass(class_file=class_file, static_fields=static_fields)
    runtime_classes[get_name_of(class_file.constant_pool, class_file.this_class)] = runtime_class

    # Look for the class initializer <clinit> to set any explicit values
    for method in class_file.methods:
        method_name = from_cp(class_file.constant_pool, method['name_index'])['bytes'].decode('utf-8')
        if method_name == '<clinit>':
            code_attr = next((attr for attr in method['attributes'] if attr['_name'] == b'Code'), None)
            if code_attr:
                # Execute the <clinit> method, which applies explicit field initializations
                execute_method(class_file, loaded_classes, code_attr['info'], runtime_classes, has_this=False)

@dataclass
class Frame:
    stack: List[Operand] # the operand stack
    local_vars: list

def execute_method(clazz : JVMClassFile, loaded_classes : Dict[str, JVMClassFile], code_attr_info : dict, runtime_classes: Dict[str, RuntimeClass], has_this=False, passed_vars : List[Operand]=[]) -> ExecutionReturnInfo:
    assert len(code_attr_info.keys()) > 0, "Code attribute is empty"
    code = code_attr_info['code']
    frame = Frame(stack=[],
                  local_vars=[])

    # Reference to 'this' object
    if has_this:
        frame.local_vars.append(Operand(type=OperandType.REFERENCE, value=0))
    # Arguments passed to the method
    for var in passed_vars:
        frame.local_vars.append(var)
    
    while len(frame.local_vars) < code_attr_info['max_locals']:
        frame.local_vars.append(None)
        
    def stack_trace():
        nonlocal frame
        print(f"--- Stack trace ---")
        pprint(frame.stack)
        print(f"--- Local vars ---")
        pprint(frame.local_vars)
        print(f"--- Runtime classes ---")
        pprint(runtime_classes)
        print(f"--- End stack trace ---")
        
    operations_count = 0
    with io.BytesIO(code) as f:
        while f.tell() < len(code):
            opcode_byte = parse_i1(f)
            try:
                opcode = Opcode(opcode_byte)
                operations_count += 1
                #print("     Stack:", frame.stack)
                print(f"{f.tell():4d} {opcode.name}")
            except ValueError:
                stack_trace()
                raise NotImplementedError(f"Unknown opcode {hex(opcode_byte)}")
            if Opcode.getstatic == opcode:
                index = parse_i2(f)
                fieldref = from_cp(clazz.constant_pool,  index)
                name_of_class = get_name_of(clazz.constant_pool, fieldref['class_index'])
                name_of_member = get_name_of(clazz.constant_pool, fieldref['name_and_type_index'])
                signature_or_type = get_type_of_member(clazz.constant_pool, fieldref['name_and_type_index'])
                if name_of_class == 'java/lang/System' and name_of_member == 'out': # TODO: this is a hack
                    frame.stack.append(Operand(type=OperandType.OBJECT, value=b"FakePrintStream"))
                # Find a field/method in a loaded class
                elif name_of_class in loaded_classes:
                    c = loaded_classes[name_of_class]
                    key = (name_of_member, signature_or_type)
                    # Check if class is initialized in the runtime
                    initialize_runtime_class(c, loaded_classes, runtime_classes)
                    # Look after a method
                    if key in c.methods_lookup:
                        raise NotImplementedError("Method not implemented")
                        # frame.stacks.append(Operand(type=OperandType.REFERENCE, value=fully_qualified_name))
                    # Look after a field
                    elif key in c.fields_lookup:
                        # Get the field value from the runtime class
                        if name_of_class not in runtime_classes:
                            raise RuntimeError(f"Class {name_of_class} not initialized")
                        if name_of_member not in runtime_classes[name_of_class].static_fields:
                            raise RuntimeError(f"Field {name_of_member} not initialized")
                        field_value = runtime_classes[name_of_class].static_fields[name_of_member]
                        frame.stack.append(field_value)
                    else:
                        raise NotImplementedError(f"Unknown getstatic {name_of_class}/{name_of_member}")
                else:
                    raise NotImplementedError(f"Unsupported member {name_of_class}/{name_of_member} in getstatic instruction")
            elif Opcode.ldc == opcode:
                index = parse_i1(f)
                v = from_cp(clazz.constant_pool, index)
                if v['tag'] == Constant.CONSTANT_String.name:
                    frame.stack.append(Operand(type=OperandType.REFERENCE, value=from_cp(clazz.constant_pool, index)))
                elif v['tag'] == Constant.CONSTANT_Integer.name:
                    frame.stack.append(Operand(type=OperandType.INT, value=v['bytes']))
                elif v['tag'] == Constant.CONSTANT_Float.name:
                    frame.stack.append(Operand(type=OperandType.FLOAT, value=v['bytes']))
                else:
                    raise NotImplementedError(f"Unsupported constant {v['tag']} in ldc instruction")
            elif Opcode.invokevirtual == opcode:
                index = parse_i2(f)
                methodref = from_cp(clazz.constant_pool, index)
                name_of_class = get_name_of(clazz.constant_pool, methodref['class_index'])
                name_of_member = get_name_of(clazz.constant_pool, methodref['name_and_type_index']);
                if name_of_class == 'java/io/PrintStream' and name_of_member in ('print', 'println'):
                    if len(frame.stack) < 2:
                        raise RuntimeError('{name_of_class}/{name_of_member} expectes 2 arguments, but provided {n}')
                    obj = frame.stack[-2]
                    if obj.value != b'FakePrintStream':
                        raise NotImplementedError(f"Unsupported stream type {obj.value}")
                    arg = frame.stack[-1]
                    
                    end_str = '\n' if name_of_member == 'println' else ''
                    if arg.type == OperandType.REFERENCE:
                        if arg.value['tag'] == 'CONSTANT_String':
                            constant_string = from_cp(clazz.constant_pool, arg.value['string_index'])['bytes']
                            print(constant_string.decode('utf-8'), end=end_str)
                        else:
                            raise NotImplementedError(f"println for {arg.value['tag']} is not implemented")
                    elif arg.type == OperandType.INT:
                        print(arg.value, end=end_str)
                    elif arg.type == OperandType.FLOAT:
                        r_value = str(round(arg.value, 5))
                        print(r_value, end=end_str)
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
                dynamic_cp = from_cp(clazz.constant_pool, cp_index)
                assert dynamic_cp['tag'] == Constant.CONSTANT_InvokeDynamic.name, "invokedynamic index is not CONSTANT_InvokeDynamic"

                name_and_type = from_cp(clazz.constant_pool, dynamic_cp['name_and_type_index'])
                method_name = clazz.constant_pool[name_and_type['name_index']-1]['bytes'].decode('utf-8')
                method_signature = clazz.constant_pool[name_and_type['descriptor_index']-1]['bytes'].decode('utf-8')
                
                bootstrap_method_attr = from_bsm(clazz, dynamic_cp['bootstrap_method_attr_index'])
                print('bootstrap_method_attr', bootstrap_method_attr)
                class_index = from_cp(clazz.constant_pool, from_cp(clazz.constant_pool, bootstrap_method_attr['bootstrap_method_ref'])['reference_index'])['class_index']
                class_name = get_name_of(clazz.constant_pool, class_index)
                referenced_class = loaded_classes[class_name]
                print(f"invokedynamic {class_name} | {method_name} | {method_signature}")
                key = (method_name, method_signature)
                method = referenced_class.methods_lookup[key]
                print(f"Bootstrap method: {bootstrap_method_attr}")
                print(f"Name and type: {name_and_type}")
                
                raise NotImplementedError("invokedynamic is not implemented")
            elif Opcode.invokestatic == opcode:
                indexbyte1 = parse_u1(f)
                indexbyte2 = parse_u1(f)
                cp_index = u16_to_i16((indexbyte1 << 8) + indexbyte2)
                static_cp = from_cp(clazz.constant_pool, cp_index)
                assert static_cp['tag'] == Constant.CONSTANT_Methodref.name, "invokestatic index is not CONSTANT_Methodref"
                class_index = static_cp['class_index']
                class_name = get_name_of(clazz.constant_pool, class_index)
                referenced_class = loaded_classes[class_name]
                name_and_type = from_cp(clazz.constant_pool, static_cp['name_and_type_index'])
                method_name = clazz.constant_pool[name_and_type['name_index']-1]['bytes'].decode('utf-8')
                method_signature = clazz.constant_pool[name_and_type['descriptor_index']-1]['bytes'].decode('utf-8')
                key = (method_name, method_signature)
                method = referenced_class.methods_lookup[key]
            
                parsed_signature = parse_signature(method_signature)

                code_attr = method['attributes'][0]
                assert code_attr['_name'] == b'Code', "invokestatic method is not Code"
                # pop arguments from stack
                args = []
                for arg_type in parsed_signature[0]:
                    v = frame.stack.pop()
                    assert v.type == arg_type, f"invokestatic argument type mismatch: expected {arg_type}, got {v.type}"
                    args.append(v)
                # run the method
                ret = execute_method(clazz, loaded_classes, code_attr['info'], runtime_classes, passed_vars=args)

                operations_count += ret.op_count
                # push return value to stack
                ret_v = ret.return_value
                if ret_v is not None:
                    assert parsed_signature[1] == ret_v.type, f"invokestatic return type mismatch: expected {parsed_signature[1]}, got {ret_v.type}"
                    frame.stack.append(ret_v)
            elif Opcode.invokespecial == opcode:
                # NOTE: unfinishe
                continue
            elif Opcode.bipush == opcode:
                byte = parse_i1(f)
                frame.stack.append(Operand(type=OperandType.INT, value=byte))
            elif Opcode.sipush == opcode:
                short = parse_i2(f)
                frame.stack.append(Operand(type=OperandType.INT, value=short))
            elif Opcode.pop == opcode:
                frame.stack.pop()
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
            elif Opcode.istore == opcode:
                index = parse_u1(f)
                operand = pop_expected(frame.stack, OperandType.INT)
                frame.local_vars[index] = operand
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
            elif Opcode.iload == opcode:
                index = parse_u1(f)
                frame.stack.append(frame.local_vars[index])
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
            elif Opcode.aload_0 == opcode:
                objectref = frame.local_vars[0]
                assert objectref.type == OperandType.REFERENCE, f"Expected reference, but got {objectref.type}"
                frame.stack.append(objectref)
            elif Opcode.aload_1 == opcode:
                objectref = frame.local_vars[1]
                assert objectref.type == OperandType.REFERENCE, f"Expected reference, but got {objectref.type}"
                frame.stack.append(objectref)
            elif Opcode.aload_2 == opcode:
                objectref = frame.local_vars[2]
                assert objectref.type == OperandType.REFERENCE, f"Expected reference, but got {objectref.type}"
                frame.stack.append(objectref)
            elif Opcode.aload_3 == opcode:
                objectref = frame.local_vars[3]
                assert objectref.type == OperandType.REFERENCE, f"Expected reference, but got {objectref.type}"
                frame.stack.append(objectref)
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
            elif Opcode.ireturn == opcode:
                return ExecutionReturnInfo(op_count=operations_count, return_value=pop_expected(frame.stack, OperandType.INT))
            elif Opcode.freturn == opcode:
                return ExecutionReturnInfo(op_count=operations_count, return_value=pop_expected(frame.stack, OperandType.FLOAT))
            elif Opcode.areturn == opcode:
                return ExecutionReturnInfo(op_count=operations_count, return_value=pop_expected(frame.stack, OperandType.REFERENCE))
            elif Opcode.lreturn == opcode:
                return ExecutionReturnInfo(op_count=operations_count, return_value=pop_expected(frame.stack, OperandType.LONG))
            elif Opcode.dreturn == opcode:
                return ExecutionReturnInfo(op_count=operations_count, return_value=pop_expected(frame.stack, OperandType.DOUBLE))
            elif Opcode.return_op == opcode:
                return ExecutionReturnInfo(op_count=operations_count)
            elif Opcode.nop == opcode:
                pass
            elif Opcode.putstatic == opcode:
                index = parse_i2(f)
                fieldref = from_cp(clazz.constant_pool,  index)
                name_of_class = get_name_of(clazz.constant_pool, fieldref['class_index'])
                name_of_member = get_name_of(clazz.constant_pool, fieldref['name_and_type_index'])
                signature_or_type = get_type_of_member(clazz.constant_pool, fieldref['name_and_type_index'])
                initialize_runtime_class(clazz, loaded_classes, runtime_classes)
                
                value = frame.stack.pop()
                # Put the value in the static field
                if name_of_class not in runtime_classes:
                    raise RuntimeError(f"Class {name_of_class} not initialized")
                runtime_class = runtime_classes[name_of_class]
                if name_of_member not in runtime_class.static_fields:
                    raise RuntimeError(f"Field {name_of_member} not initialized")
                runtime_class.static_fields[name_of_member] = value
            else:
                raise NotImplementedError(f"Opcode {opcode} is not implemented")
            
            #print(f.tell(), '==>')
            #print(frame.stack)
            #print("Local variables:")
            #pprint(frame.local_vars)
        raise Exception("Reached end of method without an op_return")


def run_class_main(main_class : JVMClassFile, loaded_classes : Dict[str, JVMClassFile]):
    assert main_class.methods is not None, "Main class has no methods"
    runtime_classes : Dict[str, RuntimeClass] = {}
    for method in  main_class.methods:
        method_name = from_cp(main_class.constant_pool, method['name_index'])['bytes'].decode('utf-8')
        if method_name not in ('main'): continue    # NOTE: should we run some (static) init method?
        for attr in method['attributes']:
            if attr['_name'] == AttributeInfoName.CODE.value:
                print(f"   Method {method_name}")
                code_attr = attr['info']
                assert 'code' in code_attr, "Code attribute has no code"
                start_timer = perf_counter_ns()
                exec_info = execute_method(main_class, loaded_classes, code_attr, runtime_classes, has_this=method_name == '<init>')
                end_timer = perf_counter_ns()
                print(f"   Executed {exec_info.op_count} operations in {(end_timer - start_timer) / 1000000:.2f} ms")


def load_class_from_file(file_path : str) -> Tuple[JVMClassFile, Dict[str, JVMClassFile]]:
    main_class_name = file_path.split('.')[0]
    main_class = parse_class_file(file_path)
    all_classes : Dict[str, JVMClassFile] = {main_class_name: main_class}
    for i, const in enumerate(main_class.constant_pool):
        if const['tag'] == Constant.CONSTANT_Class.name:    
            if (i+1) == main_class.this_class:
                continue # Skip main class, we already have it
            name_index = const['name_index']
            class_name = from_cp(main_class.constant_pool, name_index)['bytes'].decode('utf-8')
            
            path_prefix = ""
            if 'java/' in class_name:
                print(f"Found java class {class_name}")
                path_prefix = 'java.base/'
                if 'String' not in class_name:
                    continue # NOTE: skip java classes for now
            
            all_classes[class_name] = parse_class_file(path_prefix + class_name + '.class')
            print("Loaded class:", class_name)
            #pprint(all_classes[name_index])
    return main_class, all_classes

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
    
    main_class, loaded_classes = load_class_from_file(file_path)
    
    
    #print_constant_pool(main_class.constant_pool, expand=True)
    '''
    print('Attributes:')
    pprint(main_class.attributes)
    print('Methods:')
    pprint(main_class.methods)
    '''
    
    run_class_main(main_class, loaded_classes)