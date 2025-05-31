# Development Workflow for FreeCAD Nodes Workbench MCP Tools

This document outlines the iterative process for developing new MCP (Model Context Protocol) tools that interact with the FreeCAD Nodes workbench.

## Development Steps

The following process should be followed for each new tool identified in the `docs/nodes_tools_plan.md`:

### 1. Script Development and Verification (using `freecad.execute_code`)

*   **Objective**: Develop and verify a Python script that achieves the core functionality of the intended MCP tool directly within the FreeCAD environment.
*   **Method**:
    *   Utilize the existing `freecad.execute_code` MCP tool to iteratively send Python script snippets to FreeCAD.
    *   The script should directly interact with the FreeCAD Nodes workbench API (e.g., finding the Nodes editor, creating nodes, linking them, setting properties via `NodesStore` or direct scene manipulation).
    *   Use `freecad.execute_code` not only to perform actions but also to run checks and verifications. For example, after a script attempts to create a node, another `execute_code` call can be made to list nodes in the scene or check properties of the newly created node to confirm success.
    *   The `freecad.get_nodes_workbench_screenshot` tool should be used frequently to get visual feedback on the state of the Nodes editor after script execution.
    *   Continue this iterative process until the script reliably performs the desired action and provides clear feedback (e.g., success/failure messages, relevant data printed to the FreeCAD console which is captured by `execute_code`).

### 2. Change Summary Documentation

*   **Objective**: Document the working Python script and its functionality before creating the formal MCP tool.
*   **Method**:
    *   Once a working Python script is verified (from Step 1), create a concise change summary.
    *   This summary should detail:
        *   The purpose of the script/intended tool.
        *   The final, verified Python script that will be the core of the new MCP tool.
        *   Key features or functionalities achieved by the script.
        *   Any important notes, observations, or prerequisites discovered during the script development process (e.g., "Nodes workbench must be active," "Specific node types require certain initializations").
    *   Output this summary as a complete Markdown file for the `docs/changes/` directory (e.g., `docs/changes/XXX_implement_new_tool_name.md`, where XXX is the next sequential number). the user will paste this output across manually. 

### 3. MCP Tool Implementation

*   **Objective**: Integrate the verified script's logic into a new, dedicated MCP tool within the `freecad-mcp` server.
*   **Method**:
    *   Define a new tool function (e.g., `mcp_freecad_nodes_link_nodes`) in the MCP server's Python code, primarily in `src/freecad_mcp/server.py`.
    *   This new tool will typically wrap the Python script developed in Step 1. The script will be embedded as a string within the tool function and executed using `freecad.execute_code`.
    *   Parameters for the new MCP tool (e.g., `node_id_or_title`, `socket_index`) should be clearly defined. These parameters will be interpolated into the Python script string before execution. Ensure proper sanitization or quoting if necessary when embedding parameters into the script string.
    *   The tool function must handle inputs, construct the script with these inputs, call `freecad.execute_code`, and then process the results (including any output printed by the script and the success/error status from `execute_code`).
    *   The tool should return appropriate feedback to the MCP client (AI), including success/failure messages and ideally a screenshot of the Nodes workbench using `freecad.get_nodes_workbench_screenshot` after the operation.
    *   Use filesystem tools like `filesystem.edit_file` or `filesystem.write_file` to modify `src/freecad_mcp/server.py` and any other relevant server files.

### 4. Tool Testing

*   **Objective**: Verify that the newly implemented MCP tool functions correctly as an atomic operation.
*   **Method**:
    *   Call the newly created MCP tool directly with a variety of valid and potentially invalid parameters.
    *   Check the response from the tool to ensure it indicates success/failure correctly and provides the expected output (e.g., confirmation messages, screenshots, data).
    *   If the tool involves changes in FreeCAD, visually inspect the FreeCAD environment (if possible) or use `freecad.get_nodes_workbench_screenshot`, `freecad.execute_code` (to run verification scripts), or other query tools (`freecad.get_object_properties` if applicable to Nodes elements) to confirm the changes were applied correctly.
    *   Iterate on Step 3 (MCP Tool Implementation) and Step 4 if issues are found. This might involve refining the embedded Python script or the parameter handling in the MCP tool function.

This systematic approach ensures that each tool is well-tested at the script level within FreeCAD's environment before being integrated as a formal MCP tool, and then tested again in its final, callable form from the MCP server.