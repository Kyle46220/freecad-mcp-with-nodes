
# Change Summary: Script for `mcp_freecad_nodes_create_node` Tool

**Date:** $(date +%Y-%m-%d)
**Version:** (script phase)

## Overview

This document outlines the Python script developed and verified for the `mcp_freecad_nodes_create_node` MCP tool. The script successfully demonstrates the capability to programmatically create a new node of a specified type, at a given position, and with an optional title, within the FreeCAD Nodes workbench environment.

## Verified Python Script

The following script was successfully executed using the `freecad.execute_code` tool, resulting in the creation of a 'SolidBox' node with a specified title and position:

```python
# Script to create a single node
print("--- SCRIPT: Create Node Attempt ---")
import sys
import traceback 
from PySide import QtWidgets # For finding active window/scene
import FreeCADGui

# --- Parameters for the node to be created (these would be passed to the tool) ---
op_code_str = "<class 'generators_solid_box.SolidBox'>"
new_title = "MyCreatedBox_via_Script"
pos_x = 50.0
pos_y = 150.0
# --- End Parameters ---

# Initialize variables for status reporting
fcn_sub_window_widget = None
scene = None
node_created_message = "Node creation status: Unknown." # Default message

try:
    # Find active FCNSubWindow and its scene
    app = QtWidgets.QApplication.instance()
    if not app:
        node_created_message = "Error: No QApplication instance found. Cannot find Nodes editor."
        print(node_created_message)
        raise Exception(node_created_message)

    all_widgets = app.allWidgets()
    for w in all_widgets:
        if w.__class__.__name__ == 'FCNSubWindow' and w.isVisible():
            fcn_sub_window_widget = w
            break 
    
    if fcn_sub_window_widget and hasattr(fcn_sub_window_widget, 'scene'):
        scene = fcn_sub_window_widget.scene
    
    if not scene:
        node_created_message = "Error: No active FCNSubWindow (Nodes editor) with a scene found. Cannot create node."
        print(node_created_message)
        raise Exception(node_created_message)

    print(f"Found FCNSubWindow: {fcn_sub_window_widget} with scene: {scene}")

    # Import NodesStore to get node classes
    NodesStore_class = None
    try:
        from core.nodes_conf import NodesStore as NodesStoreFromImport 
        NodesStore_class = NodesStoreFromImport
        if not NodesStore_class.nodes: 
            print("NodesStore.nodes is empty, attempting to refresh...")
            NodesStore_class.refresh_nodes_list() # Ensure nodes are loaded
            if NodesStore_class.nodes:
                print(f"NodesStore.nodes refreshed. Count: {len(NodesStore_class.nodes)}")
            else:
                node_created_message = "Error: NodesStore.nodes is empty even after refresh. Cannot find node classes."
                print(node_created_message)
                raise Exception(node_created_message)
        print(f"NodesStore imported. Node count: {len(NodesStore_class.nodes)}")
    except ImportError as e_import:
        node_created_message = f"Error: Could not import NodesStore from core.nodes_conf. Details: {str(e_import)}"
        print(node_created_message)
        raise Exception(node_created_message)
    except Exception as e_ns_init: 
        node_created_message = f"Error: Exception initializing or refreshing NodesStore. Details: {str(e_ns_init)}"
        print(node_created_message)
        raise Exception(node_created_message)

    # Get the Node Class from op_code
    NodeClass = NodesStore_class.get_class_from_opcode(op_code_str)
    if not NodeClass:
        available_op_codes_sample = list(NodesStore_class.nodes.keys())[:5] # Show a sample
        node_created_message = f"Error: OpCode '{op_code_str}' not found in NodesStore. Cannot create node. Sample available op_codes: {available_op_codes_sample}"
        print(node_created_message)
        raise Exception(node_created_message)

    print(f"Got NodeClass: {NodeClass} for op_code: {op_code_str}")

    # Instantiate the node
    node_instance = NodeClass(scene)
    print(f"Node instance created: {node_instance} (ID: {node_instance.id if hasattr(node_instance, 'id') else 'N/A'})")

    # Set position
    node_instance.setPos(pos_x, pos_y)
    print(f"Node position set to: ({pos_x}, {pos_y})")

    # Set title
    actual_title_set = new_title
    if not new_title: # If title is None or empty string
        if hasattr(NodeClass, 'op_title') and NodeClass.op_title:
            actual_title_set = NodeClass.op_title # Use default op_title from class
        else:
            actual_title_set = f"Node_{node_instance.id if hasattr(node_instance, 'id') else 'UnknownID'}" # Fallback
            
    node_instance.title = actual_title_set
    print(f"Node title set to: '{actual_title_set}'")

    # Store history
    scene.history.storeHistory(f"Created node '{actual_title_set}' via MCP Script", setModified=True)
    print("History stored.")

    node_created_message = f"Successfully created node '{actual_title_set}' (type: {op_code_str}) at ({pos_x}, {pos_y})."
    print(node_created_message)

except Exception as e:
    tb_str = traceback.format_exc()
    detailed_error_message = f"Error during node creation script: {str(e)}\nTraceback:\n{tb_str}"
    print(detailed_error_message)
    # Update the main status message if it hasn't been set to a more specific error
    if node_created_message == "Node creation status: Unknown.":
        node_created_message = detailed_error_message


# Final print to ensure the status message is the last thing outputted by the script.
print("--- SCRIPT EXECUTION END ---")
print(node_created_message) 
```

## Key Features Demonstrated

*   **Scene Access**: Successfully finds the active `FCNSubWindow` and its associated `scene` object.
*   **NodeStore Usage**: Imports `NodesStore` from `core.nodes_conf` and uses it to retrieve node classes by their `op_code_str`. Includes a check and refresh for `NodesStore.nodes`.
*   **Node Instantiation**: Creates an instance of the specified node class within the active scene.
*   **Positioning**: Sets the `x` and `y` coordinates of the new node.
*   **Titling**: Sets a custom title for the node, with fallbacks if no title is provided.
*   **History and Feedback**: Stores a history event for the node creation and prints a status message to the console.
*   **Error Handling**: Includes `try-except` blocks for robust error reporting, including issues with scene/NodesStore access or node instantiation.

## Important Notes & Observations

*   The script requires the FreeCAD Nodes workbench to be active and an editor window (`FCNSubWindow`) to be open.
*   The `op_code_str` parameter (e.g., `"<class 'generators_solid_box.SolidBox'>"`) is crucial for identifying the correct node type.
*   The script dynamically imports `core.nodes_conf.NodesStore` from within the FreeCAD Python environment.
*   The parameters `op_code_str`, `new_title`, `pos_x`, and `pos_y` will be arguments to the final MCP tool.

This script forms the basis for the `mcp_freecad_nodes_create_node` MCP tool.
