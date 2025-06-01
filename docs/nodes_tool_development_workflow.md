# Development Workflow for FreeCAD Nodes Workbench MCP Tools

This document outlines the iterative process for developing new MCP (Model Context Protocol) tools that interact with the FreeCAD Nodes workbench, utilizing dedicated RPC methods in the FreeCAD addon.

## Development Steps

The following process should be followed for each new tool identified in the `docs/nodes_tools_plan.md`:

### 1. RPC Method Design & Logic Development (within FreeCAD Addon)

*   **Objective**: Design and implement the core logic for the new operation as a dedicated method within the `FreeCADRPC` class in `addon/FreeCADMCP/rpc_server/rpc_server.py`.
*   **Method**:
    *   Define the new RPC method signature (e.g., `def nodes_create_node(self, doc_name, node_type_op_code, ...):`) in `FreeCADRPC`.
    *   Implement the core logic that interacts with the FreeCAD Nodes workbench API directly within this method (or its corresponding `_gui` suffixed method if GUI interaction is needed, following the established pattern). This includes finding the Nodes editor, creating nodes, linking them, setting properties, etc.
    *   Ensure the method uses the `rpc_request_queue` and `rpc_response_queue` for GUI-related tasks, similar to existing RPC methods like `_create_object_gui`.
    *   Test this logic iteratively within the FreeCAD Python console or by temporarily calling it from an existing `execute_code` script if needed for rapid prototyping of the internal logic *before* formalizing the MCP tool.
    *   The RPC method should return a dictionary containing `{"success": True/False, "data": ..., "error": ...}` or similar structured information.

### 2. Change Summary Documentation

*   **Objective**: Document the new RPC method and its intended MCP tool functionality.
*   **Method**:
    *   Once the RPC method logic is working (from Step 1), create a concise change summary.
    *   This summary should detail:
        *   The purpose of the new RPC method and its corresponding MCP tool.
        *   The signature and a brief description of the RPC method added to `addon/FreeCADMCP/rpc_server/rpc_server.py`.
        *   Key functionalities achieved.
        *   Any important notes, observations, or prerequisites (e.g., "Nodes workbench must be active").
    *   Output this summary as a complete Markdown file for the `docs/changes/` directory (e.g., `docs/changes/XXX_implement_new_tool_name.md`).

### 3. MCP Tool Implementation (in `freecad-mcp` server)

*   **Objective**: Create a new MCP tool in `src/freecad_mcp/server.py` that calls the newly defined RPC method.
*   **Method**:
    *   Define a new tool function (e.g., `mcp_freecad_nodes_link_nodes`) in `src/freecad_mcp/server.py`.
    *   This tool function will call the corresponding new RPC method on the `FreeCADConnection` object (e.g., `freecad.nodes_link_nodes(...)`).
    *   Define clear parameters for the MCP tool. These parameters will be passed directly to the RPC method.
    *   The MCP tool function must handle the inputs, call the RPC method, and then process the structured dictionary returned by the RPC method.
    *   The tool should return appropriate feedback to the MCP client (AI), including success/failure messages derived from the RPC response, and ideally a screenshot of the Nodes workbench using `freecad.get_nodes_workbench_screenshot` (if applicable and successful).
    *   Modify `src/freecad_mcp/server.py` and `addon/FreeCADMCP/rpc_server/rpc_server.py`.

### 4. Tool and RPC Method Testing

*   **Objective**: Verify that the new RPC method and the MCP tool function correctly together as an atomic operation.
*   **Method**:
    *   Call the newly created MCP tool directly with a variety of valid and potentially invalid parameters.
    *   Check the response from the MCP tool to ensure it correctly reflects the success/failure and data from the RPC method.
    *   If the operation involves changes in FreeCAD, visually inspect the FreeCAD environment or use `freecad.get_nodes_workbench_screenshot` and other query tools to confirm the changes were applied correctly.
    *   Iterate on Step 1 (RPC Method Logic) and Step 3 (MCP Tool Implementation) if issues are found. This might involve refining the RPC method logic in the addon or the parameter handling in the MCP tool function.

This systematic approach ensures that operations are implemented robustly within the FreeCAD addon's RPC interface and then cleanly exposed as MCP tools.