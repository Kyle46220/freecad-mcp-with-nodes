# Change Summary: Script for `mcp_freecad_nodes_link_nodes` Tool

**Date:** $(date +%Y-%m-%d)
**Version:** (script phase)

## Overview

This document outlines the Python script developed and verified for the upcoming `mcp_freecad_nodes_link_nodes` MCP tool. The script successfully demonstrates the capability to programmatically create an edge (link) between specified output and input sockets of two different nodes within the FreeCAD Nodes workbench environment.

## Verified Python Script

The following script was successfully executed using the `freecad.execute_code` tool, resulting in the creation of two 'SolidBox' nodes and a link between them:

```python
# Script to create two nodes and link them
print("--- SCRIPT: Create and Link Nodes Attempt 1 ---")
import sys
import traceback # For detailed error reporting
from PySide import QtWidgets
import FreeCADGui

# Initialize variables
fcn_sub_window_widget = None
scene = None
link_message = "Link status unknown." # Default message

try:
    # Find active FCNSubWindow and its scene
    app = QtWidgets.QApplication.instance()
    if app:
        all_widgets = app.allWidgets()
        for w in all_widgets:
            # Accessing class name via __class__.__name__
            if w.__class__.__name__ == 'FCNSubWindow' and w.isVisible():
                fcn_sub_window_widget = w
                break # Found the active FCNSubWindow
    
    if fcn_sub_window_widget and hasattr(fcn_sub_window_widget, 'scene'):
        scene = fcn_sub_window_widget.scene
    
    if not scene:
        link_message = "Error: No active FCNSubWindow (Nodes editor) with a scene found. Cannot proceed."
        print(link_message)
        # To ensure this error stops the script if running in an environment that doesn't auto-exit:
        raise Exception(link_message) 

    print(f"Found FCNSubWindow: {fcn_sub_window_widget} with scene: {scene}")

    # Import NodesStore to get node classes
    NodesStore_class = None
    try:
        # Assuming 'core' is in a path accessible by FreeCAD's Python
        from core.nodes_conf import NodesStore as NodesStoreFromImport 
        NodesStore_class = NodesStoreFromImport
        if not NodesStore_class.nodes: # If nodes list is empty, try to refresh
            print("NodesStore.nodes is empty, attempting to refresh...")
            NodesStore_class.refresh_nodes_list()
            if NodesStore_class.nodes:
                print(f"NodesStore.nodes refreshed. Count: {len(NodesStore_class.nodes)}")
            else:
                # If still empty, this is a problem for creating nodes by opcode.
                link_message = "Error: NodesStore.nodes is empty even after refresh. Cannot get node classes."
                print(link_message)
                raise Exception(link_message)
        print("NodesStore imported and nodes list available.")
    except ImportError as e_import:
        link_message = f"Error: Could not import NodesStore from core.nodes_conf. Details: {str(e_import)}"
        print(link_message)
        raise Exception(link_message)
    except Exception as e_ns_init: # Catch other potential errors during NodesStore access
        link_message = f"Error: Exception initializing or refreshing NodesStore. Details: {str(e_ns_init)}"
        print(link_message)
        raise Exception(link_message)

    # --- Node Creation Part (for testing purposes) ---
    solid_box_opcode = "<class 'generators_solid_box.SolidBox'>" 
    NodeClass = NodesStore_class.get_class_from_opcode(solid_box_opcode)
    
    if not NodeClass:
        link_message = f"Error: Could not get NodeClass for opcode '{solid_box_opcode}'. Check if this node type is registered."
        print(link_message)
        raise Exception(link_message)

    # Create Node A
    node_A = NodeClass(scene)
    node_A.setPos(100, 100)
    node_A.title = "Box_A_LinkTest" 
    scene.history.storeHistory("Created Box_A_LinkTest via MCP Script", setModified=True)
    print(f"Node '{node_A.title}' (ID: {node_A.id}) created.")

    # Create Node B
    node_B = NodeClass(scene)
    node_B.setPos(400, 100) 
    node_B.title = "Box_B_LinkTest"
    scene.history.storeHistory("Created Box_B_LinkTest via MCP Script", setModified=True)
    print(f"Node '{node_B.title}' (ID: {node_B.id}) created.")

    # --- Linking Part ---
    source_node_title_to_find = "Box_A_LinkTest"
    source_socket_index_to_use = 0 # 'Shape' output for SolidBox
    target_node_title_to_find = "Box_B_LinkTest"
    target_socket_index_to_use = 0 # 'Width' input for SolidBox

    # Find node instances by title
    src_node_instance_found = None
    tgt_node_instance_found = None
    for n_instance in scene.nodes:
        if hasattr(n_instance, 'title'):
            if n_instance.title == source_node_title_to_find:
                src_node_instance_found = n_instance
            if n_instance.title == target_node_title_to_find:
                tgt_node_instance_found = n_instance
    
    if not src_node_instance_found:
        link_message = f"Error: Source node '{source_node_title_to_find}' not found in scene."
        print(link_message)
        raise Exception(link_message)
    if not tgt_node_instance_found:
        link_message = f"Error: Target node '{target_node_title_to_find}' not found in scene."
        print(link_message)
        raise Exception(link_message)

    print(f"Found source node: '{src_node_instance_found.title}' (ID: {src_node_instance_found.id})")
    print(f"Found target node: '{tgt_node_instance_found.title}' (ID: {tgt_node_instance_found.id})")

    # Get sockets from the found instances
    if not src_node_instance_found.outputs or source_socket_index_to_use >= len(src_node_instance_found.outputs):
        link_message = f"Error: Source socket index {source_socket_index_to_use} is out of range for node '{src_node_instance_found.title}'. Available outputs: {len(src_node_instance_found.outputs)}"
        print(link_message)
        raise Exception(link_message)
    src_socket_to_use = src_node_instance_found.outputs[source_socket_index_to_use]

    if not tgt_node_instance_found.inputs or target_socket_index_to_use >= len(tgt_node_instance_found.inputs):
        link_message = f"Error: Target socket index {target_socket_index_to_use} is out of range for node '{tgt_node_instance_found.title}'. Available inputs: {len(tgt_node_instance_found.inputs)}"
        print(link_message)
        raise Exception(link_message)
    tgt_socket_to_use = tgt_node_instance_found.inputs[target_socket_index_to_use]
    
    src_socket_type_str = src_socket_to_use.socket_str_type if hasattr(src_socket_to_use, 'socket_str_type') else type(src_socket_to_use).__name__
    tgt_socket_type_str = tgt_socket_to_use.socket_str_type if hasattr(tgt_socket_to_use, 'socket_str_type') else type(tgt_socket_to_use).__name__
    print(f"Source socket: Index {source_socket_index_to_use}, Type: {src_socket_type_str}")
    print(f"Target socket: Index {target_socket_index_to_use}, Type: {tgt_socket_type_str}")

    # Import Edge class
    try:
        from nodeeditor.node_edge import Edge 
        print("Successfully imported 'Edge' from nodeeditor.node_edge.")
    except ImportError as e_edge_import:
        link_message = f"Error: Could not import Edge class from nodeeditor.node_edge. Details: {str(e_edge_import)}"
        print(link_message)
        raise Exception(link_message)

    # Create the edge (link)
    new_edge = Edge(scene, src_socket_to_use, tgt_socket_to_use) 
    scene.history.storeHistory(f"Linked '{src_node_instance_found.title}' to '{tgt_node_instance_found.title}' via MCP Script", setModified=True)
    
    link_message = f"Successfully linked '{src_node_instance_found.title}' output socket {source_socket_index_to_use} to '{tgt_node_instance_found.title}' input socket {target_socket_index_to_use}."
    print(link_message)

except Exception as e:
    tb_str = traceback.format_exc()
    detailed_error_message = f"Error during script execution: {str(e)}\nTraceback details:\n{tb_str}"
    print(detailed_error_message)
    if link_message == "Link status unknown.": 
        link_message = detailed_error_message

print("--- SCRIPT EXECUTION END ---")
print(link_message) 
```

## Key Features Demonstrated

*   **Scene Access**: Successfully finds the active `FCNSubWindow` and its associated `scene` object.
*   **NodeStore Usage**: Imports `NodesStore` from `core.nodes_conf` and uses it to retrieve node classes by their `op_code`. Includes a check and refresh for `NodesStore.nodes`.
*   **Node Creation**: Creates two `generators_solid_box.SolidBox` nodes with custom titles and positions for testing the linking functionality.
*   **Node Identification**: Locates the created nodes within the scene by their titles.
*   **Socket Access**: Accesses the `inputs` and `outputs` lists of the node instances to retrieve specific sockets by index.
*   **Edge Creation**: Imports the `Edge` class from `nodeeditor.node_edge` and instantiates it, passing the scene, source socket, and target socket to create a visual and logical link.
*   **History and Feedback**: Stores history events for node creation and linking, and prints status messages to the console.
*   **Error Handling**: Includes `try-except` blocks to catch and report errors during script execution, including import errors and issues with node/socket access.

## Important Notes & Observations

*   The script assumes the FreeCAD Nodes workbench is active and has an open editor window (`FCNSubWindow`).
*   Node identification by title is used. For a robust MCP tool, providing unique node IDs (if available and stable) or more specific selectors might be preferable if titles are not guaranteed to be unique by the user.
*   Socket identification by index is used. The MCP tool will need parameters for these indices (or potentially socket names if they are reliable identifiers).
*   The `op_code` for `SolidBox` is `"<class 'generators_solid_box.SolidBox'>"`. The script uses this string literal.
*   The script relies on the standard structure of node objects having `inputs` and `outputs` lists (attributes) containing socket objects, and these socket objects being compatible with the `nodeeditor.node_edge.Edge` constructor.

This script provides a solid foundation for the `mcp_freecad_nodes_link_nodes` tool.
