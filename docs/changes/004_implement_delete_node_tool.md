# 004 - Implement `mcp_freecad_nodes_delete_node` Tool

**Date:** 2025-05-31

## Purpose

This change implements the `mcp_freecad_nodes_delete_node` MCP tool. This tool allows for the programmatic deletion of a specified node from the FreeCAD Nodes workbench graph.

## Key Features

-   Deletes a node from the graph.
-   Supports identifying the node by its unique ID or its user-defined title.
-   Handles removal of associated edges connected to the deleted node (typically managed by the node's delete mechanism).
-   Provides feedback on the success or failure of the deletion operation.
-   Includes a screenshot of the Nodes workbench after the operation.

## Parameters

-   `node_id_or_title: str`: The ID or title of the node to be deleted.

## Core Python Script Logic (Embedded in MCP Tool)

The core logic involves finding the specified node within the active FreeCAD Nodes scene. Once found, the script calls the node's deletion method (e.g., `node.delete()` or `scene.removeNode(node)`), which is expected to handle its removal from the scene and cleanup of any connected edges. Error handling is included for scenarios like the node not being found. The full script is embedded within the MCP tool definition in `src/freecad_mcp/server.py`.

## Testing Considerations (Conceptual)

-   Create a node.
-   Attempt to delete it using its title or ID. Verify success and its disappearance from the screenshot.
-   Create a node, connect it with edges, then delete it. Verify the node and its associated edges are removed.
-   Attempt to delete a non-existent node. Verify failure message.

## Notes

- The script assumes that the node object's `delete()` method or the scene's `removeNode()` method correctly handles all aspects of node removal, including unlinking and deleting any connected edges. This is typical behavior in node graph libraries like Nodz.
