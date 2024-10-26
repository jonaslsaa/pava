# Pava

## Overview

Pava is a simple, educational Java Virtual Machine (JVM) interpreter written in Python. It aims to emulate core JVM functionality by parsing and executing Java `.class` files, including loading classes, handling the constant pool, and interpreting bytecode instructions. This project was inspired by [JelloVM](https://github.com/tsoding/JelloVM) by tsoding.

While Pava doesn’t cover the full JVM specification, it handles a variety of Java bytecode instructions, making it a valuable tool for learning about JVM internals.

## Directory Structure

```
├── Main.java                 # Sample Java main class for testing
├── README.md                 # Project documentation
├── java.base                 # Directory for built-in Java classes
│   └── .keep                 # Placeholder file
├── jvmconsts.py              # Constants for the JVM, including opcodes and flags
├── jvmparser.py              # JVM class file parser and attribute handlers
├── main.py                   # Main interpreter program
├── useful                    # Useful documentation links
│   ├── Chapter 4. The class File Format.webloc
│   └── Chapter 6. The Java Virtual Machine Instruction Set.webloc
└── utils.py                  # Utility functions for byte parsing
```

## Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/username/pava
   cd pava
   ```
   
2. **Requirements**
   - Ensure you have Python 3.x installed.
   - Install dependencies if needed (e.g., `dataclasses`, `enum`, `typing`, `io` for more advanced features).

## Usage

To execute a Java `.class` file, use the following command from the repository root:

```bash
python3 main.py path/to/Main.class
```

> **Note**: The interpreter requires the `.class` file format, not `.java` source files. You can compile `.java` files with `javac Main.java` and run `python3 main.py Main.class`.

## Project Components

### 1. `jvmconsts.py`
This module contains constants for various JVM opcodes, attribute types, and access flags.

### 2. `jvmparser.py`
Responsible for parsing `.class` files, this module reads bytecode, builds a constant pool, and handles class methods, fields, and attributes. Highlights include:
   - `parse_class_file()`: Loads a class file, parsing the constant pool and main class structures.
   - `parse_constant_pool()`: Reads constants (e.g., `CONSTANT_Methodref`, `CONSTANT_Class`).
   - `parse_attributes()`: Interprets JVM attributes like `Code`, `SourceFile`, and `LineNumberTable`.

### 3. `main.py`
The main interpreter script. It reads `.class` files, executes the main method by interpreting bytecode instructions, and supports basic Java I/O operations.

### 4. `utils.py`
Contains helper functions for parsing binary data (e.g., `parse_u1`, `parse_i2`) and type conversions essential for decoding the `.class` file structure.

## Current Features

- **Basic Bytecode Execution**: Supports a variety of JVM instructions (e.g., `getstatic`, `invokevirtual`, `ldc`, `return`).
- **Class and Method Loading**: Dynamically loads classes and methods referenced in the bytecode.
- **Constant Pool Handling**: Parses and manages the constant pool, enabling access to constants within a `.class` file.
- **Error Handling**: Detects unsupported operations and provides informative runtime errors.

## Limitations

Pava is limited to a subset of JVM features. Advanced features like garbage collection, multi-threading, and full `invokedynamic` support are not implemented.

## Roadmap

- **Enhanced Bytecode Support**: Expand the opcode coverage for more complex Java programs.
- **Improved Standard Library Emulation**: Support additional standard Java classes and methods.
- **Optimization**: Refine the interpreter for better performance on complex code.
