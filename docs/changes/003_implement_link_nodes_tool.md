# 003 - Implement `mcp_freecad_nodes_link_nodes` Tool

**Date:** 2025-05-31

## Purpose

This change implements the `mcp_freecad_nodes_link_nodes` MCP tool. This tool allows for the programmatic connection (linking) of an output socket of a source node to an input socket of a target node within the FreeCAD Nodes workbench.

## Key Features

-   Connects two nodes via specified sockets.
-   Supports identifying nodes by their unique ID or their user-defined title.
-   Supports identifying sockets by their index (integer as string) or their name (string).
-   Provides feedback on the success or failure of the linking operation.
-   Includes a screenshot of the Nodes workbench after the operation.

## Parameters

-   `source_node_id_or_title: str`: The ID or title of the source node.
-   `source_socket_index_or_name: str`: The index (e.g., "0", "1") or name of the output socket on the source node.
-   `target_node_id_or_title: str`: The ID or title of the target node.
-   `target_socket_index_or_name: str`: The index (e.g., "0", "1") or name of the input socket on the target node.

## Core Python Script Logic (Embedded in MCP Tool)

The core logic involves finding the specified nodes and sockets within the active FreeCAD Nodes scene. It then checks for compatibility and uses the Nodes workbench's internal API (e.g., `Edge` class from `nodz_main` or `Nodes.nodz_main`) to create and register the connection. Error handling is included for scenarios like missing nodes/sockets or connection failures. The full script is embedded within the MCP tool definition in `src/freecad_mcp/server.py`.

## Testing Considerations (Conceptual)

-   Create two compatible nodes.
-   Attempt to link them using valid titles/IDs and socket indices/names. Verify success and visual link in screenshot.
-   Attempt to link incompatible sockets. Verify failure message.
-   Attempt to link non-existent nodes or sockets. Verify failure message.

## Notes

- The script relies on the structure of the FreeCAD Nodes workbench, particularly how nodes, sockets, and scenes are accessed and manipulated (e.g., `scene.nodes`, `node.outputs`, `socket.can_connect_to`, `Edge` class instantiation).
- Socket identification tries both direct name match and matching string representation of index.
