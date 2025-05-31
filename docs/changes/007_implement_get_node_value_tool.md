# 007 - Implement `mcp_freecad_nodes_get_node_value` Tool

**Date:** 2025-05-31

## Purpose

This change implements the `mcp_freecad_nodes_get_node_value` MCP tool. This tool is designed to retrieve values from output sockets or potentially direct properties of specified nodes within the FreeCAD Nodes workbench.

## Key Features

-   Identifies the target node by its unique ID or user-defined title.
-   Identifies the target output socket by its index (integer as string) or its name/label (string). The parameter also allows for a property path, though current implementation focuses on output sockets.
-   Returns the retrieved value as a JSON string if successful.
-   Returns a descriptive error message if the node, socket, or value cannot be retrieved, or if the value is not JSON serializable.
-   Does not include a workbench screenshot, focusing on returning the data or error status.

## Parameters

-   `node_id_or_title: str`: The ID or title of the target node.
-   `output_socket_index_or_name_or_property_path: str`: The index, name/label of the output socket, or a (currently basic) property path.

## Returns

The tool returns a list containing a single `TextContent` item.
-   **On Success:** The `text` field of the `TextContent` will be a JSON string representing the retrieved value (e.g., `"hello"`, `123`, `[1, 2]`).
-   **On Failure:** The `text` field will contain an error message, typically prefixed with "ERROR:".

## Core Python Script Logic (Embedded in MCP Tool)

The core logic, embedded as a Python script, executes the following:
1.  Finds the active FreeCAD Nodes editor scene.
2.  Locates the specified target node by its ID or title.
3.  Attempts to find the specified output socket on the target node by index or by matching its name/label (checking common attributes like `name`, `title()`, `label()`, `socket_name`, and considering `valOutputs` and `outputs` lists).
4.  If an output socket is found, it attempts to retrieve its value using common accessor methods/attributes (e.g., `socket.value()`, `socket.getValue()`, `socket.currentValue`, `socket.val`).
5.  The retrieved value is then serialized to a JSON string using `json.dumps()`. This JSON string is the primary output of the script on success.
6.  If any step fails (node/socket not found, value retrieval fails, value not JSON serializable), an appropriate error message is generated as the script's output.
7.  The MCP tool captures the last non-empty line of the script's output as the result.

## Testing Considerations (Conceptual)

-   Test retrieving values from various types of output sockets (string, number, boolean, list).
-   Test identifying nodes by ID and by title.
-   Test identifying output sockets by index and by name/label.
-   Test with invalid node/socket identifiers to verify error messages.
-   Test with sockets whose values might be complex or non-JSON-serializable to observe error handling.
-   Test on different types of nodes to ensure compatibility of value retrieval methods.

## Notes

- The current implementation primarily focuses on retrieving values from *output sockets*. While the parameter name suggests property path access, this is noted as a potential future enhancement and is not fully implemented in the initial version beyond basic socket attribute checks.
- The script relies on common accessor patterns for socket values. The exact methods/attributes (`value()`, `getValue()`, `currentValue`, `val`) might vary for specific socket types in the Nodes workbench.
