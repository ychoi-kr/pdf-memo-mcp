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
-   **Clear Documentation (Docstrings)**: The tool's usage, including the **expected format and constraints of its arguments**, must be clearly documented in its tool schema so the AI agent can learn how to use it correctly.

---

#### C. ~~Unified and Complete Data~~ **Multiple Access Patterns for Flexibility**

> ⚙️ **Principle: Provide multiple complementary approaches that work together seamlessly.**

-   **Hybrid Architecture**: The tool should provide both **MCP Resources** for precise file selection and **intuitive Tools** for natural language interaction. This gives AI agents multiple ways to accomplish the same goal based on context.
-   **Unified Annotation Processing**: Regardless of the access method (Resource or Tool), the underlying annotation extraction should use a **single, complete data structure** that combines the strengths of various libraries (e.g., `PyPDF2`, `pdfplumber`) to provide consistent, comprehensive results.
-   **Complementary Tools**: Instead of providing multiple, fragmented tools for the same core function, offer **complementary tools that work at different levels of specificity** - from broad search to precise URI-based access.

---

#### D. Structured Data Exchange

> 📦 **Principle: Always communicate with the AI agent using a machine-readable format like JSON.**

-   **JSON First**: The tool must always respond to the AI agent using a **pure JSON format**, not human-readable, pre-formatted text.
-   **Benefits**: Structured data is more **efficient** for the AI to parse, more **reliable** as it prevents data loss, and more **flexible**, allowing the agent to easily reuse and reformat the data for various follow-up requests.

---

#### E. **User Experience Through AI Agency**

> 🤖 **Principle: Design tools that enable natural AI interactions while maintaining technical precision.**

-   **Natural Language Support**: Tools should accept keywords and partial matches (e.g., "CS interview notes") while maintaining strict validation for security and reliability.
-   **Graceful Degradation**: When the AI cannot find files through natural language, provide clear alternatives like file listing tools rather than forcing exact file paths.
-   **Context Preservation**: Tools should provide enough context (file paths, timestamps, etc.) for the AI to make intelligent decisions and provide meaningful user feedback.

***

### 3. Implementation Guidelines

#### File Access Patterns
1. **Resource-Based**: For clients that can present file lists for user selection
2. **Search-Based**: For natural language queries that need intelligent file matching  
3. **Direct URI**: For precise access when file location is already known

#### Error Handling
- Fail fast with clear, actionable error messages
- Never expose system internals or security-sensitive information
- Provide alternative approaches when primary method fails

#### Security Model
- Maintain strict sandbox boundaries regardless of access method
- Validate all inputs before processing
- Log security-relevant events for monitoring

***

### 4. Conclusion

By adhering to these principles, we can build a high-quality MCP server that is not just functional, but also robust, secure, and a trusted component within the broader AI agent ecosystem. The hybrid approach ensures maximum compatibility with different client capabilities while maintaining consistent behavior and security standards.
