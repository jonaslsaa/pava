from dataclasses import dataclass
from enum import Enum, auto
from io import BufferedReader
from typing import Any, List, Tuple, Union
from pprint import pprint

from jvmconsts import *
from utils import *

@dataclass
class JVMClassFile:
    version : Tuple[int, int]
    constant_pool : List[dict]
    methods : List[dict]
    methods_lookup : dict
    attributes : List[dict]
    access_flags : List[str]
    this_class : int
    super_class : int
    interfaces : List[dict]
    fields : List[dict]

class AttributeInfoName(Enum):
    BOOTSTRAP_METHOD = b'BootstrapMethods'
    INNER_CLASSES = b'InnerClasses'
    SOURCE_FILE = b'SourceFile'
    CODE = b'Code'
    LINE_NUMBER_TABLE = b'LineNumberTable'
    STACK_MAP_TABLE = b'StackMapTable'

def get_name_of_class(clazz, class_index: int) -> str:
    return clazz.constant_pool[clazz.constant_pool[class_index - 1]['name_index'] - 1]['bytes'].decode('utf-8')

def get_name_of_member(clazz, name_and_type_index: int) -> str:
    return clazz.constant_pool[clazz.constant_pool[name_and_type_index - 1]['name_index'] - 1]['bytes'].decode('utf-8')

CACHED_ATTR_INSTANCES = {}

def from_cp(constant_pool : List[dict], index: int) -> dict:
    assert index > 0, "Constant pool index must be positive"
    return constant_pool[index - 1]

def from_bsm(clazz : JVMClassFile, index: int) -> dict:
    assert index >= 0, "Bootstrap method index must be non-negative"
    assert clazz.attributes is not None, "Bootstrap method index must be non-negative"
    bsm_info = None
    if AttributeInfoName.BOOTSTRAP_METHOD.value in CACHED_ATTR_INSTANCES:
        bsm_info = CACHED_ATTR_INSTANCES[AttributeInfoName.BOOTSTRAP_METHOD]
    else: # find the BootstrapMethods attribute
        for attr in clazz.attributes: # should be cached, as it is the only bsm
            if attr['_name'] == AttributeInfoName.BOOTSTRAP_METHOD.value:
                bsm_info = attr['info']
                CACHED_ATTR_INSTANCES[AttributeInfoName.BOOTSTRAP_METHOD] = bsm_info
    if bsm_info != None:
        return bsm_info['bootstrap_methods'][index]
    raise RuntimeError("Bootstrap method not found")

def parse_flags(value: int, flags: List[Tuple[str, int]]) -> List[str]:
    return [name for (name, mask) in flags if (value & mask) != 0]

def parse_attributes(constant_pool : List[dict], f : Union[io.BytesIO, BufferedReader], count : int) -> list:
    attributes = []
    for j in range(count):
        # attribute_info {
        #     u2 attribute_name_index;
        #     u4 attribute_length;
        #     u1 info[attribute_length];
        # }
        attribute = {}
        attribute['attribute_name_index'] = parse_i2(f)
        attribute['_name'] = from_cp(constant_pool, attribute['attribute_name_index'])['bytes']
        attribute_length = parse_i4(f)
        
        info_bytes = f.read(attribute_length)
        attribute['info'] = parse_attribute_info(constant_pool, attribute['_name'], info_bytes)
        attributes.append(attribute)
    return attributes
       
def parse_attribute_info(constant_pool : List[dict], attr_name : bytes, info_bytes) -> dict:
    attr_info_stream = io.BytesIO(info_bytes)
    try:
        attr_info_type = AttributeInfoName(attr_name)
    except ValueError:
        raise NotImplementedError(f"Attribute {attr_name} is not implemented")
    match attr_info_type:
        case AttributeInfoName.BOOTSTRAP_METHOD:
            return parse_attribute_info_BootstrapMethods(constant_pool, attr_info_stream)
        case AttributeInfoName.SOURCE_FILE:
            return parse_attribute_info_SourceFile(constant_pool, attr_info_stream)
        case AttributeInfoName.INNER_CLASSES:
            return parse_attribute_info_InnerClasses(constant_pool, attr_info_stream)
        case AttributeInfoName.CODE:
            return parse_attribute_info_Code(constant_pool, attr_info_stream)
        case AttributeInfoName.LINE_NUMBER_TABLE:
            return parse_attribute_info_LineNumberTable(constant_pool, attr_info_stream)
        case AttributeInfoName.STACK_MAP_TABLE:
            return parse_attribute_info_StackMapTable(constant_pool, attr_info_stream)
        case _:
            raise NotImplementedError(f'attribute {attr_name} is not implemented')

def parse_attribute_info_BootstrapMethods(constant_pool : List[dict], f : io.BytesIO):
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

def parse_attribute_info_SourceFile(constant_pool : List[dict], f : io.BytesIO):
    attr = {}
    attr['sourcefile_index'] = parse_i2(f)
    return attr

def parse_attribute_info_InnerClasses(constant_pool : List[dict], f : io.BytesIO):
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

def parse_attribute_info_LineNumberTable(constant_pool : List[dict], f : io.BytesIO):
    attr = {}
    attr['line_number_table_length'] = parse_i2(f)
    table = []
    for i in range(attr['line_number_table_length']):
        entry = {}
        entry['start_pc'] = parse_i2(f)
        entry['line_number'] = parse_i2(f)
        table.append(entry)
    attr['line_number_table'] = table
    return attr

def parse_attribute_info_StackMapTable(constant_pool : List[dict], f : io.BytesIO):
    attr = {}
    attr['number_of_entries'] = parse_i2(f)
    entries = []
    for i in range(attr['number_of_entries']):
        entry = {}
        entry['frame_type'] = parse_i1(f)
        if entry['frame_type'] <= 63:
            pass
        elif entry['frame_type'] <= 127:
            pass
        elif entry['frame_type'] <= 246:
            pass
        elif entry['frame_type'] <= 247:
            pass
        elif entry['frame_type'] <= 250:
            pass
        elif entry['frame_type'] <= 251:
            pass
        elif entry['frame_type'] <= 254:
            pass
        elif entry['frame_type'] <= 255:
            pass
        entries.append(entry)
    attr['entries'] = entries
    return attr

def parse_attribute_info_Code(constant_pool : List[dict], f : io.BytesIO) -> dict:
    code_attribute = {}
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
    code_attribute['attributes'] = parse_attributes(constant_pool, f, attributes_count)
    # NOTE: parsing the code attribute is not finished
    return code_attribute

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
        elif Constant.CONSTANT_Long == constant_tag:
            high_bytes = parse_i4(f)
            low_bytes = parse_i4(f)
            cp_info['bytes'] = (high_bytes << 32) + low_bytes
        elif Constant.CONSTANT_Double == constant_tag:
            high_bytes = parse_i4(f)
            low_bytes = parse_i4(f)
            cp_info['bytes'] = (high_bytes << 32) + low_bytes
        else:
            raise NotImplementedError(f"Unexpected constant tag {constant_tag} in class file.")
        cp_info['tag'] = constant_tag.name
        constant_pool.append(cp_info)
    return constant_pool

def parse_interfaces(f, interfaces_count):
    interfaces = []
    for i in range(interfaces_count):
        interface = {'index' : parse_i2(f)}
        interfaces.append(interface)
    return interfaces

def parse_fields(constant_pool, f, fields_count):
    fields = []
    for i in range(fields_count):
        field = {}
        field['access_flags'] = parse_i2(f)
        field['name_index'] = parse_i2(f)
        field['descriptor_index'] = parse_i2(f)
        attributes_count = parse_i2(f)
        field['attributes'] = parse_attributes(constant_pool, f, attributes_count)
        fields.append(field)
    return fields

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
        
        interfaces_count = int.from_bytes(f.read(2), byteorder='little')
        interfaces = parse_interfaces(f, interfaces_count)
        fields_count = int.from_bytes(f.read(2), byteorder='little')
        fields = parse_fields(constant_pool, f, fields_count)
        
        methods_count = parse_i2(f)
        methods = []
        methods_lookup = {}
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
            lookup_key = (method['name_index'], method['descriptor_index'])
            attributes_count = parse_i2(f)
            method['attributes'] = parse_attributes(constant_pool, f, attributes_count)
            methods.append(method)
            methods_lookup[lookup_key] = method
        
        attributes_count = parse_i2(f)
        attributes = parse_attributes(constant_pool, f, attributes_count)
        return JVMClassFile(version, constant_pool, methods, methods_lookup, attributes, access_flags, this_class, super_class, interfaces, fields)

def find_methods_by_name(clazz : JVMClassFile, name: bytes):
    assert clazz.methods is not None, "Class methods not parsed"
    return [method
            for method in clazz.methods
            if clazz.constant_pool[method['name_index'] - 1]['bytes'] == name]

def find_attributes_by_name(clazz : JVMClassFile, name: bytes):
    assert clazz.attributes is not None, "Class attributes not parsed"
    return [attr
            for attr in clazz.attributes
            if clazz.constant_pool[attr['attribute_name_index'] - 1]['bytes'] == name]