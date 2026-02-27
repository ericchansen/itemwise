# Orchestration Log: Mal Spec Audit

**Agent:** Mal (Lead)  
**Task:** Audit SPEC.md vs actual codebase  
**Started:** 2026-02-27T21:35:00Z  
**Status:** Completed

## Outcome
Spec is accurate for core functionality but significantly outdated in peripherals.

### Findings
- **Accurate:** Core architecture, inventory models, chat flow, OpenAI integration
- **Undocumented:** ~21 features exist in code but not in SPEC.md
- **Outdated:** 6 items (e.g., frontend described as single-file; actually modular JS + PWA)
- **Bug Found:** `get_expiring_items` tool defined but no handler in `tool_handlers` dict

### Undocumented Features
| Category | Features |
|----------|----------|
| **API Endpoints** | trash, restore, purge, expiring, expiration-digest, forgot-password, reset-password, logout, delete-account, confirm-action |
| **Database** | `deleted_at` on InventoryItem, `expiration_date` on ItemLot |
| **AI Tools** | `get_expiring_items_tool` (MCP) |
| **Security** | CSRF protection, rate limiting, cookie-based auth |
| **Email** | password reset, expiration digest |
| **Environment** | 4 new env vars (untracked) |
| **Architecture** | dual `/api/v1` + `/api` mount |

### Recommendation
Assign doc agent to rewrite SPEC.md sections 4, 5, 7, 8, 9, 10, 12, 13, 14 using this audit as checklist. Fix `get_expiring_items` handler bug separately.

### Decision Logged
→ `.squad/decisions.md` (merged from inbox)
