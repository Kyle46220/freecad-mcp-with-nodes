# Plan for Generic FreeCAD Nodes Workbench MCP Tools

**Date:** $(date +%Y-%m-%d)

## 1. Rationale

The FreeCAD Nodes workbench offers a powerful visual programming interface for parametric design. To effectively leverage this from an MCP (Model Context Protocol) server, a set of generic, low-level tools is required. These tools will provide the fundamental building blocks for more complex operations and allow the AI assistant (or other clients) to programmatically construct, modify, and query node graphs.

Instead of creating highly specific, task-oriented tools (e.g., "create_specific_cabinet_v1"), generic tools offer:
-   **Versatility**: Can be combined to create a wide variety of an_part_from_librarys and workflows, not just predefined ones.
-   **Flexibility**: Adaptable to new node types and future changes in the Nodes workbench.
-   **Maintainability**: Easier to test, debug, and maintain a smaller set of core functions.
-   **Discoverability**: Simpler for the AI to understand and utilize a few powerful primitives.

## 2. Proposed Generic Tools

The following generic tools are planned for implementation. Each will operate on the active Nodes workbench graph editor in FreeCAD.

### Core Graph Manipulation:

1.  **`mcp_freecad_nodes_create_node`**
    *   **Description**: Creates a new node of a specified type at a given position with an optional title.
    *   **Parameters**:
        *   `node_type_op_code: str` (e.g., `"<class 'generators_solid_box.SolidBox'>"`)
        *   `title: str | None`
        *   `x_pos: float`
        *   `y_pos: float`
    *   **Returns**: Success/failure message, created node ID, and a workbench screenshot.
    *   **Status**: Implemented.

2.  **`mcp_freecad_nodes_link_nodes`**
    *   **Description**: Connects an output socket of a source node to an input socket of a target node.
    *   **Parameters**:
        *   `source_node_id_or_title: str`
        *   `source_socket_index_or_name: str | int`
        *   `target_node_id_or_title: str`
        *   `target_socket_index_or_name: str | int`
    *   **Returns**: Success/failure message and a workbench screenshot.
    *   **Status**: To be implemented.

3.  **`mcp_freecad_nodes_delete_node`**
    *   **Description**: Deletes a specified node from the graph.
    *   **Parameters**:
        *   `node_id_or_title: str`
    *   **Returns**: Success/failure message and a workbench screenshot.
    *   **Status**: To be implemented.

4.  **`mcp_freecad_nodes_delete_edge`** (Alternative: or by specifying connected sockets)
    *   **Description**: Deletes a specified edge from the graph.
    *   **Parameters**:
        *   `edge_id: str` (if edges have inspectable IDs)
        *   OR `source_node_id_or_title: str`, `source_socket_index_or_name: str | int`, `target_node_id_or_title: str`, `target_socket_index_or_name: str | int`
    *   **Returns**: Success/failure message and a workbench screenshot.
    *   **Status**: To be implemented.

### Node Parameterization:

5.  **`mcp_freecad_nodes_set_node_value`**
    *   **Description**: Sets the value for a specific input socket or an internal property of a node.
    *   **Parameters**:
        *   `node_id_or_title: str`
        *   `input_socket_index_or_name_or_property_path: str | int`
        *   `value: any` (JSON serializable)
    *   **Returns**: Success/failure message and a workbench screenshot.
    *   **Status**: To be implemented.

6.  **`mcp_freecad_nodes_get_node_value`**
    *   **Description**: Retrieves the current value of a node's output socket or an internal property.
    *   **Parameters**:
        *   `node_id_or_title: str`
        *   `output_socket_index_or_name_or_property_path: str | int`
    *   **Returns**: The retrieved value or an error message.
    *   **Status**: To be implemented.

### Graph State & Utilities:

7.  **`mcp_freecad_nodes_get_graph_state`**
    *   **Description**: Returns a structured representation (e.g., JSON) of the current node graph, including nodes (ID, title, type, position, sockets) and connections.
    *   **Parameters**: None
    *   **Returns**: JSON string representing the graph state.
    *   **Status**: To be implemented.

8.  **`mcp_freecad_nodes_clear_scene`**
    *   **Description**: Clears all nodes and edges from the current Nodes workbench scene.
    *   **Parameters**: None
    *   **Returns**: Success/failure message and a workbench screenshot.
    *   **Status**: To be implemented.

9.  **`mcp_freecad_nodes_get_available_node_types`**
    *   **Description**: Returns a list of all available node `op_codes` that can be used with `create_node`.
    *   **Parameters**: None
    *   **Returns**: List of `op_code` strings.
    *   **Status**: To be implemented.

10. **`mcp_freecad_nodes_set_node_position`**
    *   **Description**: Moves an existing node to a new position.
    *   **Parameters**:
        *   `node_id_or_title: str`
        *   `x_pos: float`
        *   `y_pos: float`
    *   **Returns**: Success/failure message and a workbench screenshot.
    *   **Status**: To be implemented.

## 3. Implementation Strategy

-   Each tool will be implemented as an `@mcp.tool()` in `src/freecad_mcp/server.py`.
-   The core logic for interacting with the Nodes workbench will be encapsulated in Python scripts executed via the existing `freecad.execute_code()` method.
-   Node identification will primarily rely on unique node titles. If titles are not guaranteed to be unique by the user, an alternative using node IDs (if accessible and stable) will be explored.
-   Thorough testing of each tool's underlying script will be performed using `mcp_freecad_execute_code` before committing the MCP tool definition.
-   Each successful tool implementation will be documented in the `docs/changes/` directory.

## 4. Considerations

-   **Node Identification**: Robustly identifying specific nodes (e.g., for linking or setting values) is crucial. Titles are user-friendly but may not be unique. Internal node IDs, if accessible and persistent through MCP calls, would be more reliable.
-   **Socket Identification**: Sockets might be identified by index or by name (if names are consistent and available).
-   **Asynchronous Nature**: Operations on the FreeCAD GUI should be handled carefully, though the current `execute_code` mechanism is synchronous from the MCP server's perspective.
-   **Error Handling**: Each tool must provide clear error messages back to the MCP client. 