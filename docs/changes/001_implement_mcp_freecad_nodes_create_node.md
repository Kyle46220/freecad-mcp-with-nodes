# MCP Tool: mcp_freecad_nodes_create_node

**Date:** $(date +%Y-%m-%d)

## Purpose

This document describes the `mcp_freecad_nodes_create_node` MCP tool and its underlying RPC method `nodes_create_node`. This tool allows clients to create new nodes within the FreeCAD Nodes workbench.

## MCP Tool: `mcp_freecad_nodes_create_node`

*   **File:** `src/freecad_mcp/server.py`
*   **Description:** Creates a new node in the FreeCAD Nodes workbench.
*   **Parameters:**
    *   `node_type_op_code: str`: The type identifier string for the node to be created (e.g., `"<class 'generators_solid_box.SolidBox'>"`).
    *   `title: str | None` (optional, default: `None`): An optional title to assign to the new node.
    *   `x_pos: float` (optional, default: `0.0`): The x-coordinate for the node's position in the editor.
    *   `y_pos: float` (optional, default: `0.0`): The y-coordinate for the node's position in the editor.
*   **Returns:** A list of `TextContent` and `ImageContent` objects.
    *   `TextContent`: Contains messages indicating success or failure, including the created node's ID and title if successful.
    *   `ImageContent`: Contains a screenshot of the Nodes workbench after the operation, if available.
*   **Example Usage (JSON):**
    ```json
    {
        "tool_name": "mcp_freecad_nodes_create_node",
        "arguments": {
            "node_type_op_code": "<class 'generators_extruders_extrude.SurfaceExtrude'>",
            "title": "MyExtrudeNode",
            "x_pos": 100.0,
            "y_pos": 50.0
        }
    }
    ```

## RPC Method: `nodes_create_node`

*   **File:** `addon/FreeCADMCP/rpc_server/rpc_server.py`
*   **Class:** `FreeCADRPC`
*   **Signature:** `nodes_create_node(self, node_type_op_code: str, title: str | None, x_pos: float, y_pos: float) -> dict`
*   **Description:** This is the core method executed within FreeCAD to create the node. It handles interaction with the Nodes workbench API.
*   **Parameters:** Same as the MCP tool.
*   **Returns:** A dictionary containing:
    *   `success: bool`: True if the node was created successfully, False otherwise.
    *   `node_id: str | None`: The unique identifier of the created node (if successful).
    *   `title: str | None`: The actual title of the created node (if successful).
    *   `message: str`: A descriptive message about the outcome of the operation.
*   **Key Functionalities:**
    *   Ensures the Nodes workbench is active (attempts to activate it if available).
    *   Retrieves the active Nodes editor/graph.
    *   Dynamically imports the specified node class from its `node_type_op_code`.
    *   Calls the Nodes API to create the node with the given title and position.
    *   Handles errors gracefully and returns informative messages.

## Prerequisites

*   The FreeCAD MCP server addon must be installed and running in FreeCAD.
*   The FreeCAD Nodes workbench must be installed in FreeCAD.
*   For a node to be created, its corresponding type (`node_type_op_code`) must be available/installed in the Nodes workbench.

## Notes

*   The `node_id` returned is typically the internal name assigned by the Nodes workbench (e.g., `Node_1`).
*   The `title` returned is the display title, which might be different from the `node_id` if a custom title was provided.
*   Screenshots are best-effort; if the Nodes workbench view isn't accessible or visible, a screenshot might not be returned.
