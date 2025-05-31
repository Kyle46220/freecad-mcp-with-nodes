# 005 - Implement `mcp_freecad_nodes_delete_edge` Tool

**Date:** 2025-05-31

## Purpose

This change implements the `mcp_freecad_nodes_delete_edge` MCP tool. This tool allows for the programmatic deletion of a specific edge (connection) between two nodes in the FreeCAD Nodes workbench.

## Key Features

-   Deletes an edge connecting two specified sockets on two specified nodes.
-   Nodes are identified by ID or title.
-   Sockets are identified by index or name.
-   Provides feedback on the success or failure of the edge deletion.
-   Includes a screenshot of the Nodes workbench after the operation.

## Parameters

-   `source_node_id_or_title: str`: The ID or title of the source node of the edge.
-   `source_socket_index_or_name: str`: The index or name of the output socket on the source node.
-   `target_node_id_or_title: str`: The ID or title of the target node of the edge.
-   `target_socket_index_or_name: str`: The index or name of the input socket on the target node.

## Core Python Script Logic (Embedded in MCP Tool)

The script first locates the source and target nodes and their respective sockets within the active Nodes scene. It then iterates through the scene's edges (or edges connected to the identified sockets) to find the specific edge matching the criteria. Once found, the script calls the edge's deletion method (e.g., `edge.delete()` or `scene.removeEdge(edge)`). Error handling covers cases like missing nodes/sockets or the specified edge not being found. The full script is embedded in `src/freecad_mcp/server.py`.

## Testing Considerations (Conceptual)

-   Create two nodes and link them.
-   Attempt to delete the edge using correct node/socket identifiers. Verify success and visual removal in screenshot.
-   Attempt to delete an edge using incorrect identifiers (non-existent node, wrong socket). Verify failure message.
-   Attempt to delete an edge that does not exist between two valid nodes/sockets. Verify failure message.

## Notes

- The script assumes edges can be found by iterating `scene.edges` or `socket.edges` and checking `edge.start_socket` and `edge.end_socket`.
- Deletion relies on `edge.delete()` or `scene.removeEdge(edge)`.
