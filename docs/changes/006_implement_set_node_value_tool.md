# 006 - Implement `mcp_freecad_nodes_set_node_value` Tool

**Date:** 2025-05-31

## Purpose

This change implements the `mcp_freecad_nodes_set_node_value` MCP tool. This tool allows for setting the value of an input socket on a specified node within the FreeCAD Nodes workbench.

## Key Features

-   Identifies the target node by its unique ID or user-defined title.
-   Identifies the target input socket by its index (integer as string) or its name/label (string).
-   Accepts the value to be set as a JSON string, allowing for various data types (string, number, boolean, list, object).
-   Provides feedback on the success or failure of the value-setting operation.
-   Includes a screenshot of the Nodes workbench after the operation.

## Parameters

-   `node_id_or_title: str`: The ID or title of the target node.
-   `input_socket_index_or_name: str`: The index (e.g., "0") or name/label of the input socket.
-   `value_json: str`: A JSON string representing the value. Examples:
    -   String: `"\"hello world\""`
    -   Number: `"123.45"`
    -   Boolean: `"true"`
    -   List: `"[1, \"two\", false]"`
    -   Object: `"{\"key\": \"value\", \"num\": 10}"`

## Core Python Script Logic (Embedded in MCP Tool)

The core logic, embedded as a Python script within the MCP tool, performs the following steps:
1.  Finds the active FreeCAD Nodes editor scene.
2.  Locates the specified target node by its ID or title.
3.  Locates the specified input socket on the target node by index or by matching its name/label (checking common attributes like `name`, `title()`, `label()`, `socket_name`, and also considering `valInputs` and `inputs` lists on the node).
4.  Parses the `value_json` string into a Python object using `json.loads()`.
5.  Attempts to set the parsed value on the input socket by trying common methods such as `socket.setValue(value)` or `socket.setCurrentValue(value)`.
6.  If successful, it may attempt to trigger node/scene updates (e.g., `node.update()`, `scene.update()`) if such methods exist.
7.  Records the action in the scene's history.
8.  Provides detailed feedback messages for success or various error conditions (node/socket not found, JSON parsing error, value setting error).

## Testing Considerations (Conceptual)

-   Test setting string, integer, float, boolean, list, and simple object values on appropriate input sockets.
-   Test identifying nodes by ID and by title.
-   Test identifying sockets by index and by name/label.
-   Test with invalid node/socket identifiers to verify error handling.
-   Test with malformed JSON strings to verify parsing error handling.
-   Test on different types of nodes and input sockets to ensure compatibility.

## Notes

- The tool focuses on setting values for *input* sockets.
- The embedded script relies on common methods and attributes found in Node/Socket objects within Nodz-based frameworks (like FreeCAD's Nodes workbench, e.g., `setValue`, `setCurrentValue`, `valInputs`, `inputs`). The exact attributes and methods might vary slightly depending on the specific node and socket implementation.
- The `value_json` parameter in the MCP tool is passed to the embedded script such that the script receives it as a string literal, ready for `json.loads()`.
