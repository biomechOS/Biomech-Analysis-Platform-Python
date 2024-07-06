from typing import Any

import tomli as tomllib
import json

from ResearchOS.overhaul.constants import DATA_OBJECT_NAME_KEY, LOAD_CONSTANT_FROM_FILE_KEY, LOGSHEET_KEY, DATA_FILE_KEY
from ResearchOS.overhaul.custom_classes import InputVariable, Constant, DataObjectName, Unspecified, DataFilePath, LoadConstantFromFile, LogsheetVariable
from ResearchOS.overhaul.helper_functions import is_dynamic_variable, is_specified

def classify_input_type(input: Any):
    """Takes in an input from a TOML file and spits out the class of the input."""
    attrs = {}

    if not is_specified(input):
        return Unspecified, attrs
    
    if isinstance(input, str):
        if input.startswith("__"):
            if input == DATA_OBJECT_NAME_KEY:
                return DataObjectName, attrs
            if input.startswith(LOGSHEET_KEY):
                return LogsheetVariable, attrs
        if is_dynamic_variable(input):
            return InputVariable, attrs
        attrs = {'value': input}
        return Constant, attrs
    
    if isinstance(input, dict):
        if len(input.keys()) != 1:
            attrs['value'] = input
            return Constant, attrs
        key = list(input.keys())[0]
        if key == LOAD_CONSTANT_FROM_FILE_KEY:
            attrs['value'] = load_constant_from_file(input[key])
            return LoadConstantFromFile, attrs
        if key == DATA_FILE_KEY:
            return DataFilePath, attrs

    attrs['value'] = input
    return Constant, attrs

def load_constant_from_file(file_name: str) -> Any:
    """Load a constant from a file."""
    if file_name.endswith('.toml'):
        with open(file_name, 'rb') as f:
            value = tomllib.load(f)
    elif file_name.endswith('.json'):
        with open(file_name, 'rb') as f:
            value = json.load(f)
    return value