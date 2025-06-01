# Plan for Generic FreeCAD Nodes Workbench MCP Tools

**Date:** $(date +%Y-%m-%d)

## 1. Rationale

The FreeCAD Nodes workbench offers a powerful visual programming interface for parametric design. To effectively leverage this from an MCP (Model Context Protocol) server, a set of generic, low-level tools is required. These tools will provide the fundamental building blocks for more complex operations and allow the AI assistant (or other clients) to programmatically construct, modify, and query node graphs.

Instead of creating highly specific, task-oriented tools (e.g., "create_specific_cabinet_v1"), generic tools offer:
-   **Versatility**: Can be combined to create a wide variety of designs and workflows.
-   **Flexibility**: Adaptable to new node types and future changes in the Nodes workbench.
-   **Maintainability**: Easier to test, debug, and maintain a smaller set of core functions by centralizing logic in the FreeCAD addon's RPC server.
-   **Discoverability**: Simpler for the AI to understand and utilize a few powerful primitives.

## 2. Proposed Generic Tools

The following generic tools are planned for implementation. Each MCP tool will call a corresponding dedicated method in the `FreeCADRPC` class within the FreeCAD addon.

### Core Graph Manipulation:

1.  **`mcp_freecad_nodes_create_node`**
    *   **Description**: Creates a new node of a specified type at a given position with an optional title.
    *   **MCP Tool Parameters**:
        *   `node_type_op_code: str` (e.g., `"<class 'generators_solid_box.SolidBox'>"`)
        *   `title: str | None`
        *   `x_pos: float`
        *   `y_pos: float`
    *   **RPC Method (in `addon/FreeCADMCP/rpc_server/rpc_server.py`)**: `nodes_create_node(self, node_type_op_code, title, x_pos, y_pos)`
    *   **Returns**: Structured dictionary with success/failure, created node ID/details, and a workbench screenshot (if applicable).
    *   **Status**: To be refactored to use dedicated RPC method.

2.  **`mcp_freecad_nodes_link_nodes`**
    *   **Description**: Connects an output socket of a source node to an input socket of a target node.
    *   **MCP Tool Parameters**:
        *   `source_node_id_or_title: str`
        *   `source_socket_index_or_name: str | int`
        *   `target_node_id_or_title: str`
        *   `target_socket_index_or_name: str | int`
    *   **RPC Method**: `nodes_link_nodes(self, source_node_id_or_title, source_socket_index_or_name, target_node_id_or_title, target_socket_index_or_name)`
    *   **Returns**: Structured dictionary with success/failure message and a workbench screenshot.
    *   **Status**: To be implemented.

3.  **`mcp_freecad_nodes_delete_node`**
    *   **Description**: Deletes a specified node from the graph.
    *   **MCP Tool Parameters**:
        *   `node_id_or_title: str`
    *   **RPC Method**: `nodes_delete_node(self, node_id_or_title)`
    *   **Returns**: Structured dictionary with success/failure message and a workbench screenshot.
    *   **Status**: To be refactored/implemented.

4.  **`mcp_freecad_nodes_delete_edge`**
    *   **Description**: Deletes a specified edge from the graph, identified by its connected sockets.
    *   **MCP Tool Parameters**:
        *   `source_node_id_or_title: str`
        *   `source_socket_index_or_name: str | int`
        *   `target_node_id_or_title: str`
        *   `target_socket_index_or_name: str | int`
    *   **RPC Method**: `nodes_delete_edge(self, source_node_id_or_title, source_socket_index_or_name, target_node_id_or_title, target_socket_index_or_name)`
    *   **Returns**: Structured dictionary with success/failure message and a workbench screenshot.
    *   **Status**: To be refactored/implemented.

### Node Parameterization:

5.  **`mcp_freecad_nodes_set_node_value`**
    *   **Description**: Sets the value for a specific input socket of a node.
    *   **MCP Tool Parameters**:
        *   `node_id_or_title: str`
        *   `input_socket_index_or_name: str | int`
        *   `value_json: str` (JSON string representing the value)
    *   **RPC Method**: `nodes_set_node_value(self, node_id_or_title, input_socket_index_or_name, value_json)`
    *   **Returns**: Structured dictionary with success/failure message and a workbench screenshot.
    *   **Status**: To be refactored/implemented.

6.  **`mcp_freecad_nodes_get_node_value`**
    *   **Description**: Retrieves the current value of a node's output socket.
    *   **MCP Tool Parameters**:
        *   `node_id_or_title: str`
        *   `output_socket_index_or_name: str | int`
    *   **RPC Method**: `nodes_get_node_value(self, node_id_or_title, output_socket_index_or_name)`
    *   **Returns**: Structured dictionary with success/failure and the retrieved value (JSON serializable) or an error message.
    *   **Status**: To be refactored/implemented.

### Graph State & Utilities:

7.  **`mcp_freecad_nodes_get_graph_state`**
    *   **Description**: Returns a structured representation (e.g., JSON) of the current node graph.
    *   **MCP Tool Parameters**: None
    *   **RPC Method**: `nodes_get_graph_state(self)`
    *   **Returns**: JSON string representing the graph state or an error message.
    *   **Status**: To be implemented.

8.  **`mcp_freecad_nodes_clear_scene`**
    *   **Description**: Clears all nodes and edges from the current Nodes workbench scene.
    *   **MCP Tool Parameters**: None
    *   **RPC Method**: `nodes_clear_scene(self)`
    *   **Returns**: Structured dictionary with success/failure message and a workbench screenshot.
    *   **Status**: To be implemented.

9.  **`mcp_freecad_nodes_get_available_node_types`**
    *   **Description**: Returns a list of all available node `op_codes` that can be used with `create_node`.
    *   **MCP Tool Parameters**: None
    *   **RPC Method**: `nodes_get_available_node_types(self)`
    *   **Returns**: List of `op_code` strings or an error message.
    *   **Status**: To be implemented.

10. **`mcp_freecad_nodes_set_node_position`**
    *   **Description**: Moves an existing node to a new position.
    *   **MCP Tool Parameters**:
        *   `node_id_or_title: str`
        *   `x_pos: float`
        *   `y_pos: float`
    *   **RPC Method**: `nodes_set_node_position(self, node_id_or_title, x_pos, y_pos)`
    *   **Returns**: Structured dictionary with success/failure message and a workbench screenshot.
    *   **Status**: To be implemented.

## 3. Implementation Strategy

-   Each MCP tool will be implemented as an `@mcp.tool()` in `src/freecad_mcp/server.py`.
-   The core logic for interacting with the Nodes workbench will be encapsulated in new, dedicated methods within the `FreeCADRPC` class in `addon/FreeCADMCP/rpc_server/rpc_server.py`.
-   The MCP tool in `src/freecad_mcp/server.py` will call its corresponding RPC method via the `FreeCADConnection` object.
-   Node identification will primarily rely on unique node titles or IDs. The RPC methods will handle the logic to find nodes based on the provided identifier.
-   Thorough testing will involve verifying the RPC method's behavior within FreeCAD and then testing the MCP tool's end-to-end functionality.
-   Each successful tool implementation (both RPC method and MCP tool) will be documented in the `docs/changes/` directory as per the updated workflow.

## 4. Considerations

-   **Node and Socket Identification**: The RPC methods must robustly handle finding nodes and sockets by ID or title/name.
-   **Structured Returns**: RPC methods should return structured dictionaries (e.g., `{"success": True, "data": ..., "error": None}`) to be processed by the MCP tool, rather than relying on string parsing of `stdout`.
-   **Error Handling**: Clear and structured error information should propagate from the RPC method to the MCP tool and then to the client.
-   **GUI Thread Safety**: All FreeCAD GUI operations within RPC methods must be queued using the `rpc_request_queue` and `rpc_response_queue` pattern established in `rpc_server.py`. 