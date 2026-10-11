# Operations Handbook

Day-to-day reference for running the service: limits, errors, and logs.

## Rate Limits

Chat endpoints are limited to 10 requests per minute per client. Exceeding the limit returns HTTP 429 with the error code RATE_LIMIT_EXCEEDED, and clients should wait for the time given in the Retry-After header before trying again.

The agent endpoint shares the same limit. Long-running agent requests still count as a single request.

## Agent Limits

An agent run stops after 5 tool-calling iterations, set by AGENT_MAX_ITERATIONS. When the limit is reached, the run ends with the stop reason `max_iterations` and the user receives the best answer available so far.

Each tool call times out after 30 seconds, set by TOOL_TIMEOUT_SECONDS. A timed-out tool returns an error result to the model, which can then answer without it or try a different tool.

## Error Codes

When MongoDB is unreachable, the API returns HTTP 503 with the error code DATABASE_UNAVAILABLE. This usually means the database container is down or the connection string in MONGODB_URI is wrong.

Unexpected server errors return HTTP 500 with the error code INTERNAL_SERVER_ERROR. The response never includes the exception message, so internal details such as connection strings are not leaked to clients.

Validation failures return HTTP 422 with a list of the fields that failed.

## Logging

Logs are written to standard output as JSON, one object per line. Every log line carries the request ID, and logs written during an agent run also carry the run ID and the user ID.

Each request ends with a "Request completed" log that includes the route, status code, duration in milliseconds, and the number of language-model calls and tokens used. Failed agent runs log the step that failed, such as `llm`, `tools`, or `save_history`.

## Token Usage

Token usage is aggregated per user per day in the `token_usage` collection. Users can read their own usage from the usage endpoint, which returns daily totals for up to 365 days.
