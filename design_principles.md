## PDF Annotator MCP Server Design Principles

### 1. Objective

This document defines the core design principles for the development, maintenance, and extension of the `PDF Annotator` MCP server. The objective is to create a **predictable, secure, and professional-grade tool** that can be used efficiently and reliably by AI agents.

***

### 2. Core Design Principles

#### A. Clear Separation of Concerns

> 🛡️ **Principle: The tool is responsible for data; the AI is responsible for interaction and presentation.**

-   **Tool (MCP Server)**: The tool's responsibility ends with retrieving, processing, and **providing data in a structured format**. The tool should not be concerned with how the data is presented to the end-user.
-   **AI Agent**: The agent is responsible for interpreting the structured data received from the tool and then **presenting it in the most appropriate format** based on the user's conversational context.

---

#### B. Predictable and Explicit Behavior

> 🔒 **Principle: The tool must not guess. It should operate explicitly as documented.**

-   **No Guessing**: The tool must not try to interpret ambiguous inputs, such as file paths. If an input is invalid, it should fail clearly and predictably (e.g., "File not found").
-   **Security First**: When accessing the file system, the tool must **never access directories outside of its allowed sandbox**. The convenience of handling a malformed path must not compromise system security.
-   **Clear Documentation (Docstrings)**: The tool's usage, including the **expected format and constraints of its arguments**, must be clearly documented in its docstring so the AI agent can learn how to use it correctly.

---

#### C. Unified and Complete Data

> ⚙️ **Principle: Provide complete and consistent information in a single tool call.**

-   **Single Source of Truth**: The tool should serve as a single source of truth. It should combine the strengths of various libraries (e.g., `PyPDF2`, `pdfplumber`) to create a **single, complete data structure** that contains all the information the AI needs (e.g., note content, original text, position).
-   **Unified Tools**: Instead of providing multiple, fragmented tools, the goal is to offer a **single, powerful tool for a core function**. The AI agent should not have to guess which "annotation" tool to use; it should be able to call the primary tool and trust that it will receive the best possible result every time.

---

#### D. Structured Data Exchange

> 📦 **Principle: Always communicate with the AI agent using a machine-readable format like JSON.**

-   **JSON First**: The tool must always respond to the AI agent using a **pure JSON format**, not human-readable, pre-formatted text.
-   **Benefits**: Structured data is more **efficient** for the AI to parse, more **reliable** as it prevents data loss, and more **flexible**, allowing the agent to easily reuse and reformat the data for various follow-up requests.

***

### 3. Conclusion

By adhering to these principles, we can build a high-quality MCP server that is not just functional, but also robust, secure, and a trusted component within the broader AI agent ecosystem.
