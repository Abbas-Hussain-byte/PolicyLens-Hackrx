"""API types for frontend consumption."""

# This file documents the API contract between backend and frontend.
# The actual TypeScript types are in frontend/src/lib/types.ts

API_ENDPOINTS = {
    "health": "GET /api/health",
    "root": "GET /",

    # Policies
    "upload_policy": "POST /api/policies/upload (multipart/form-data)",
    "list_policies": "GET /api/policies/",
    "get_policy": "GET /api/policies/{policy_id}",
    "delete_policy": "DELETE /api/policies/{policy_id}",

    # Queries
    "ask_question": "POST /api/query/ask",
    "check_eligibility": "POST /api/query/eligibility",
    "find_exclusions": "POST /api/query/exclusions?policy_id={policy_id}",
    "batch_query": "POST /api/query/batch",

    # Compare
    "compare_policies": "POST /api/compare/",
}
