import os
import uuid

import networkx as nx
import tomli as tomllib

from ResearchOS.constants import PACKAGES_PREFIX, PROCESS_NAME, PLOT_NAME, STATS_NAME, BRIDGES_KEY, PACKAGE_SETTINGS_KEY, SUBSET_KEY, SOURCES_KEY, TARGETS_KEY
from ResearchOS.helper_functions import parse_variable_name
from ResearchOS.custom_classes import Process, Stats, Plot, OutputVariable, InputVariable, LogsheetVariable, Constant, Unspecified
from ResearchOS.input_classifier import classify_input_type
from ResearchOS.dag_info import check_variable_properly_specified

def bridge_dynamic_variables(dag: nx.MultiDiGraph, package_name: str, bridge_name: str, source: str, targets: list, package_names: list):
    """Bridge from a source (output) variable in one package to a target (input) variable in another package.
    If the target variable is Unspecified, then the 'node' attribute is converted to an InputVariable type."""
    try:
        source_node = [n['node'] for _, n in dag.nodes(data=True) if n['node'].name == source and type(n['node']) == OutputVariable][0]
    except Exception:
        source_package, source_runnable, source_variable = parse_variable_name(source)
        check_variable_properly_specified(dag, source_package, source_runnable, source_variable)                    

    for target in targets:
        target_type, tmp = classify_input_type(target)  
        assert target_type == InputVariable, f"Target type is {target_type}."        
        target_package, target_runnable, target_variable = parse_variable_name(target)
        try:
            target_node = [n['node'] for _, n in dag.nodes(data=True) if n['node'].name == target and type(n['node']) in [Unspecified, InputVariable]][0]
        except Exception as e:
            check_variable_properly_specified(dag, target_package, target_runnable, target_variable)
            raise e
        if isinstance(target_node, Unspecified):
            target_node = InputVariable(target_node.id, target_node.name, {})
        dag.nodes[target_node.id]['node'] = target_node
        dag.add_edge(source_node.id, target_node.id, bridge = package_name + "." + bridge_name)
    return dag

def bridge_packages(dag: nx.MultiDiGraph, all_packages_bridges: dict = None) -> nx.MultiDiGraph:
    """Read each package's bridges.toml file and connect the nodes in the DAG accordingly."""
    package_names_str = os.environ['PACKAGE_NAMES']
    package_names = package_names_str.split('.')
    for package_name, package_bridges in all_packages_bridges.items():
        for bridge_name, bridges_dict in package_bridges.items():
            sources = bridges_dict[SOURCES_KEY]
            targets = bridges_dict[TARGETS_KEY]            
            sources = [sources] if not isinstance(sources, list) else sources
            targets = [targets] if not isinstance(targets, list) else targets

            for source in sources:
                source_type, attrs = classify_input_type(source)
                if source_type == InputVariable:
                    dag = bridge_dynamic_variables(dag, package_name, bridge_name, source, targets, package_names)
                elif source_type == LogsheetVariable:
                    continue
                    raise NotImplementedError("LogsheetVariable is not implemented yet.")
                elif isinstance(source, Constant):
                    dag.nodes[source.id]['node']['value'] = attrs['value']                
    return dag

def discover_packages(packages_parent_folders: list = None) -> list:
    """Return a list of all packages in the specified folders.
    Packages are folders within the specified folders that start with `ros-`.
    `pyproject.toml` files are expected to be in the root of each package folder.
    Returned folders are relative or absolute, depending on the input."""

    if not packages_parent_folders:
        raise ValueError('No package folders specified.')
    
    if isinstance(packages_parent_folders, str):
        packages_parent_folders = [packages_parent_folders]
    
    packages_folders = []
    for folder in packages_parent_folders:
        folder.replace('/', os.sep)
        if not os.path.isdir(folder):
            continue  # Skip if not a directory
        for item in os.listdir(folder):
            if item.startswith(PACKAGES_PREFIX):                                
                # Get the full path for this file
                item = os.path.join(folder, item)
                packages_folders.append(item)
    return packages_folders

def get_package_index_path(package_folder_path: str) -> str:
    """Get the path (relative to the project root folder, which contains pyproject.toml) to the package index.toml file from pyproject.toml, `tool.researchos.index`.
    The default path is `index.toml` because it sits next to the `pyproject.toml` file."""
    pyproject_path = os.path.join(package_folder_path, 'pyproject.toml')
    with open(pyproject_path, 'rb') as f:
        pyproject_dict = tomllib.load(f)
    return os.path.join(package_folder_path, pyproject_dict['tool']['researchos']['index'])

def get_package_index_dict(package_folder_path: str) -> dict:
    """Get the paths for the package's processes, plots, and stats from the index.toml file.
    Dict keys are `processes`, `plots`, and `stats`. Values are lists of relative file paths (relative to package root folder)."""
    index_path = get_package_index_path(package_folder_path)
    with open(index_path, 'rb') as f:
        index_dict = tomllib.load(f)
    for key in index_dict:
        if not isinstance(index_dict[key], list):
            index_dict[key] = index_dict[key].replace('/', os.sep)
        else:
            index_dict[key] = [path.replace('/', os.sep) for path in index_dict[key]]
    # Validate the keys in the index_dict
    allowed_keys = [PROCESS_NAME, PLOT_NAME, STATS_NAME, BRIDGES_KEY, PACKAGE_SETTINGS_KEY, SUBSET_KEY]
    wrong_keys = [key for key in index_dict if key not in allowed_keys] 
    if wrong_keys:
        raise ValueError(f"Invalid keys in the index.toml file: {wrong_keys}.")
    return index_dict

def get_runnables_in_package(package_folder: str = None, paths_from_index: list = None) -> dict:
    """Get the package's processes, given the paths to the processes.toml files (from the index.toml).
    Call this function by indexing into the output of `get_package_index_dict` as the second argument.
    Valid keys are `processes`, `plots`, and `stats`.
    TODO: This is the place to validate & standardize the attributes returned by each runnable. For example, if missing 'level', fill it. 
    Same with 'batch', 'language', and other optional attributes"""
    if not package_folder:
        raise ValueError('No package specified.')
    if not paths_from_index:
        return []
    
    all_runnables_dict = {}
    for path in paths_from_index:
        path = os.path.join(package_folder, path)
        with open(path, 'rb') as f:
            runnables_dict = tomllib.load(f)
        for runnable in runnables_dict:
            # Validate & standardize each runnables_dict!
            curr_dict = runnables_dict[runnable]
            if "level" not in curr_dict:
                curr_dict["level"] = "Trial"
            if "batch" not in curr_dict:
                curr_dict["batch"] = curr_dict["level"]
            if "path" not in curr_dict:
                raise ValueError(f"Path not found in {path}.")
            if "subset" not in curr_dict:
                raise ValueError(f"Subset not found in {path}.")
            if "inputs" not in curr_dict:
                raise ValueError(f"Inputs not found in {path}.")
            if "outputs" not in curr_dict:
                raise ValueError(f"Outputs not found in {path}.")
            curr_dict["path"] = curr_dict["path"].replace('/', os.sep)
            runnables_dict[runnable] = curr_dict
        all_runnables_dict.update(runnables_dict)
    return all_runnables_dict

def get_package_bridges(package_folder: str = None, paths_from_index: list = None) -> dict:
        """Load the bridges for the package from the package's bridges.toml file."""
        if not package_folder:
            raise ValueError('No package specified.')
        
        if not paths_from_index:
            return {}
        
        all_bridges_dict = {}
        for path in paths_from_index:
            path = os.path.join(package_folder, path)            
            if not os.path.isfile(path):
                continue
            with open(path, 'rb') as f:
                bridges_dict = tomllib.load(f)
            all_bridges_dict.update(bridges_dict)
        return all_bridges_dict

def create_package_dag(package_runnables_dict: dict, package_name: str = "") -> nx.MultiDiGraph:
    """Create a directed acyclic graph (DAG) of the package's runnables.
    runnable name format: `package_name.runnable_name`
    variable format: `package_name.runnable_name.variable_name`"""

    package_dag = nx.MultiDiGraph()
    runnable_classes = {PROCESS_NAME: Process, PLOT_NAME: Plot, STATS_NAME: Stats}    
    # 1. Create a node for each runnable and input/output variable.
    # Also connect the inputs and outputs to each runnable. Still need to connect the variables between runnables after this.
    # process, plot, stats
    variable_nodes = {}
    for runnable_type, runnables in package_runnables_dict.items():
        runnable_class = runnable_classes[runnable_type]
        variable_nodes[runnable_type] = {}
        # Add each node
        for runnable_name, runnable_dict in runnables.items():
            runnable_node_uuid = str(uuid.uuid4())
            runnable_node_name = package_name + "." + runnable_name
            node = runnable_class(runnable_node_uuid, runnable_node_name, runnable_dict)
            package_dag.add_node(runnable_node_uuid, node = node)
            variable_nodes[runnable_type][runnable_name] = {}
            variable_nodes[runnable_type][runnable_name]['inputs'] = {}
            variable_nodes[runnable_type][runnable_name]['outputs'] = {}
            for input_var_name in runnable_dict['inputs']:
                input_node_uuid = str(uuid.uuid4())
                input_node_name = runnable_node_name + "." + input_var_name
                input_class, input_attrs = classify_input_type(runnable_dict['inputs'][input_var_name])
                node = input_class(input_node_uuid, input_node_name, input_attrs)
                package_dag.add_node(input_node_uuid, node = node)
                package_dag.add_edge(input_node_uuid, runnable_node_uuid)
                # is_dag = nx.is_directed_acyclic_graph(package_dag)
                variable_nodes[runnable_type][runnable_name]['inputs'][input_var_name] = node
            for output_var_name in runnable_dict['outputs']:
                output_node_uuid = str(uuid.uuid4())
                output_node_name = runnable_node_name + "." + output_var_name
                node = OutputVariable(output_node_uuid, output_node_name, {})
                package_dag.add_node(output_node_uuid, node = node)
                package_dag.add_edge(runnable_node_uuid, output_node_uuid)
                # is_dag = nx.is_directed_acyclic_graph(package_dag)

    # 2. Create edges between runnables' variables.
    for runnable_type, runnables in package_runnables_dict.items():
        # Add each node
        for runnable_name, runnable_dict in runnables.items():
            runnable_node_name = package_name + "." + runnable_name
            for input_var_name in runnable_dict['inputs']:
                target_var_node = variable_nodes[runnable_type][runnable_name]['inputs'][input_var_name]
                if type(target_var_node) != InputVariable:
                    continue

                source_var_name = package_name + "." + runnable_dict['inputs'][input_var_name]
                source_var_node = [n['node'] for _, n in package_dag.nodes(data=True) if n['node'].name == source_var_name and isinstance(n['node'], OutputVariable)][0]
                package_dag.add_edge(source_var_node.id, target_var_node.id)
                # is_dag = nx.is_directed_acyclic_graph(package_dag)
    return package_dag