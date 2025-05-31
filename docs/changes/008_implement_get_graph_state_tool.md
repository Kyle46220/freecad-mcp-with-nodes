# 008 - Implement `mcp_freecad_nodes_get_graph_state` Tool

**Date:** 2025-05-31

## Purpose

This change implements the `mcp_freecad_nodes_get_graph_state` MCP tool. This tool retrieves a comprehensive JSON representation of the current state of the graph in the FreeCAD Nodes workbench.

## Key Features

-   Iterates through all nodes in the active Nodes scene.
-   For each node, it captures:
    -   Unique ID (`id`)
    -   User-defined title (`title`)
    -   Node type/class (`type`), preferring `op_code` if available.
    -   Position in the graph editor (`position`: {x, y}).
    -   Details of its input sockets (`inputs`), including name, index, source list (`valInputs` or `inputs`), and type (if available).
    -   Details of its output sockets (`outputs`), similarly including name, index, source list (`valOutputs` or `outputs`), and type (if available).
-   Iterates through all edges (connections) in the scene.
-   For each edge, it captures:
    -   Source node ID (`source_node_id`)
    -   Source socket name (`source_socket_name`) and index (`source_socket_index`).
    -   Target node ID (`target_node_id`)
    -   Target socket name (`target_socket_name`) and index (`target_socket_index`).
-   The collected data is serialized into a single JSON string.
-   Includes error handling for scenarios like no active scene or issues during data serialization (using a custom JSON encoder for graceful handling of non-standard types).

## Parameters

-   None. The tool operates on the currently active Nodes graph in FreeCAD.

## Returns

-   A list containing a single `TextContent` item:
    -   **On Success:** The `text` field contains a JSON string representing the entire graph state.
    -   **On Failure:** The `text` field contains a JSON string with an "error" key describing the issue (e.g., no active scene, serialization problems).

## Core Python Script Logic (Embedded in MCP Tool)

The embedded Python script performs these main actions:
1.  Locates the active Nodes workbench scene.
2.  Initializes a dictionary to hold `nodes` and `edges` lists.
3.  Iterates over `scene.nodes`:
    -   For each node, extracts ID, title, type (from `op_code` or class name), and position.
    -   Iterates over the node's input sockets (checking common list attributes like `inputs` and `valInputs`), extracting name (trying `name`, `label()`, `title()`, `socket_name`), index, and type (if available).
    -   Similarly iterates over output sockets.
    -   Stores this information in a node dictionary and appends it to the `nodes` list.
4.  Iterates over `scene.edges`:
    -   For each edge, extracts source/target node IDs and source/target socket names and indices.
    -   Stores this in an edge dictionary and appends it to the `edges` list.
5.  Serializes the entire graph data dictionary to a JSON string using `json.dumps()`, employing a custom `SafeJSONEncoder` to handle potentially non-standard data types by converting them to strings or specific representations (like for QPointF).
6.  The final JSON string (or an error JSON) is printed, which is then captured by the MCP tool.

## Testing Considerations (Conceptual)

-   Call the tool on an empty graph: should return valid JSON with empty `nodes` and `edges` lists.
-   Call on a graph with several nodes but no edges: verify all nodes and their socket details are present.
-   Call on a graph with nodes and multiple edges: verify nodes and edges are correctly represented.
-   Test with nodes of different types to ensure type information is captured.
-   Inspect the JSON output for correctness and completeness.
-   Consider nodes with unusual characters in titles or socket names (though standard MCP string handling should cover this).
