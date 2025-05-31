# 009 - Implement `mcp_freecad_nodes_clear_scene` Tool

**Date:** 2025-05-31

## Purpose

This change implements the `mcp_freecad_nodes_clear_scene` MCP tool. This tool provides a way to remove all nodes and edges from the currently active scene in the FreeCAD Nodes workbench.

## Key Features

-   Identifies the active Nodes workbench scene.
-   Attempts to clear the scene using available methods:
    -   Prefers direct scene methods like `scene.clear()` or `scene.reset()` if found.
    -   As a fallback, manually iterates through all nodes in `scene.nodes` and deletes each one (which should also remove connected edges).
-   Provides feedback on the success or failure of the clearing operation.
-   Includes a screenshot of the Nodes workbench after the operation to visually confirm the state.
-   Records the action in the scene's history log.

## Parameters

-   None. The tool operates on the currently active Nodes graph.

## Core Python Script Logic (Embedded in MCP Tool)

The embedded Python script executes the following steps:
1.  Finds the active FCNSubWindow (Nodes editor) and its associated scene object.
2.  If a scene is found, it attempts to clear it:
    -   First, it checks for and calls `scene.clear()` if available.
    -   If not, it checks for and calls `scene.reset()`.
    -   If neither direct method is available, it iterates through a copy of the `scene.nodes` list and calls `node.delete()` (or `scene.removeNode(node)`) for each node. This manual deletion relies on the node's deletion mechanism to also handle removal of its connected edges.
3.  After a successful clear operation, it attempts to record this action in the scene's history.
4.  The script prints status messages indicating the method used and the outcome (success, warning if nodes/edges remain after manual deletion, or error if no method was found or an exception occurred).

## Testing Considerations (Conceptual)

-   Create a graph with several nodes and edges.
-   Call `mcp_freecad_nodes_clear_scene`.
-   Verify that the scene is empty, either visually through the returned screenshot or by subsequently calling `mcp_freecad_nodes_get_graph_state` and checking for empty nodes/edges lists.
-   Test on an already empty scene to ensure it handles this gracefully.
