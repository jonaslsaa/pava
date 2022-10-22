from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, List, Tuple, Union
from pprint import pprint

from jvmconsts import *
from utils import *

@dataclass
class JVMClass:
    version : Tuple[int, int]
    constant_pool : List[dict]
    methods : List[dict]
    attributes : List[dict]
    access_flags : List[str]
    this_class : int
    super_class : int

class AttributeInfoName(Enum):
    BOOTSTRAP_METHOD = b'BootstrapMethods'
    INNER_CLASSES = b'InnerClasses'
    SOURCE_FILE = b'SourceFile'

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

def parse_flags(value: int, flags: List[Tuple[str, int]]) -> List[str]:
    return [name for (name, mask) in flags if (value & mask) != 0]

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

def print_constant_pool(constant_pool : List[dict], expand : bool = False):
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
        
        access_flags = parse_flags(parse_i2(f), CLASS_ACCESS_FLAGS)
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
            method['access_flags'] = parse_flags(parse_i2(f), METHOD_ACCESS_FLAGS)
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